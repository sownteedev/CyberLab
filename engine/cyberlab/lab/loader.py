import copy
from dataclasses import replace
from ipaddress import IPv4Address
import json
from importlib.resources import files
from pathlib import Path
import re

import yaml
from jsonschema import Draft202012Validator

from cyberlab.assessment_goals import COMPARE_OPERATORS, INTEGER_OPERATORS, HASH_OPERATORS, evaluate_boolean_expression, integer_value

from .models import (
    Assessment,
    AssessmentArtifact,
    AssessmentGoal,
    AssessmentResult,
    Lab,
    LabMetadata,
    LabSettings,
    Network,
    Node,
    NodeResources,
    FileMapping,
    NodeUser,
    Documentation,
    Parameter, ParameterOperation,
    QuizQuestion,
)
from .documentation import snapshot_documentation, validate_documentation
from .environment import validate_environment
from .networking import validate_networking
from .assets import AssetError, snapshot_lab, validate_mappings
from .dependencies import validate_node_dependencies


MAX_DEFINITION_BYTES = 1024 * 1024
API_VERSION = "cyberlab.ptit/v1"
WORKSPACE_PATH = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.?/)[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)*$")
PARAMETER_TOKEN = re.compile(r"(?:\{\{param:[a-z][a-z0-9]*(?:-[a-z0-9]+)*\}\}|\$\{PARAM:[a-z][a-z0-9]*(?:-[a-z0-9]+)*\})")


class LabError(Exception):
    """Base error for loading a Lab definition."""


class LabReadError(LabError):
    """The requested definition cannot be read."""


class LabValidationError(LabError):
    """The definition is not valid for the supported Lab format."""


def _quiz_items(document):
    if "quiz" in document and "quizzes" in document:
        raise LabValidationError("Use either /quiz or /quizzes, not both")
    if "quizzes" in document:
        groups = document["quizzes"]
    else:
        groups = [{"id": "default", "title": "", "items": document.get("quiz", [])}]

    items = []
    group_identities = set()
    identities = set()
    for group in groups:
        group_id = group["id"]
        if group_id in group_identities:
            raise LabValidationError(f"Duplicate quiz group identity at /quizzes/{group_id}")
        group_identities.add(group_id)
        group_title = group.get("title", "")
        group_items = group.get("items", [])
        group_questions = set()
        group_question_indexes = {}
        for item_index, item in enumerate(group_items):
            identifier = item["id"]
            if identifier in identities:
                raise LabValidationError(f"Duplicate quiz identity at /{group_id}/items/{identifier}")
            identities.add(identifier)
            item_type = item.get("type", "choice")
            if item_type == "preface":
                items.append(QuizQuestion(
                    id=identifier, question="", options=(), item_type="preface",
                    text=item["text"], quiz_id=group_id, quiz_title=group_title,
                    pre_start=bool(group.get("pre_start", False)),
                ))
                if len(items) > 64:
                    raise LabValidationError("Quiz items exceed the 64 item limit")
                continue
            if item_type == "true_false":
                answer = item.get("answer")
                if answer is not None and type(answer) is not bool:
                    raise LabValidationError(f"True/False answer must be boolean at /{group_id}/items/{identifier}/answer")
                options = ("Sai", "Đúng")
                answer_index = None if answer is None else int(answer)
            else:
                answer_index = item.get("answer")
                options = tuple(item["options"])
            if item_type != "true_false" and answer_index is not None and answer_index >= len(options):
                raise LabValidationError(f"Quiz answer is outside options at /{group_id}/items/{identifier}/answer")
            prerequisite = item.get("prerequisite")
            if prerequisite is not None and prerequisite == identifier:
                raise LabValidationError(f"Quiz prerequisite cannot reference itself at /{group_id}/items/{identifier}")
            group_questions.add(identifier)
            group_question_indexes[identifier] = item_index
            items.append(QuizQuestion(
                id=identifier, question=item["question"], options=options,
                answer=answer_index, explanation=item.get("explanation", ""),
                item_type=item_type, right_response=item.get("right_response", ""),
                wrong_response=item.get("wrong_response", ""), prerequisite=prerequisite,
                quiz_id=group_id, quiz_title=group_title,
                pre_start=bool(group.get("pre_start", False)),
            ))
            if len(items) > 64:
                raise LabValidationError("Quiz items exceed the 64 item limit")
        for item_index, item in enumerate(group_items):
            prerequisite = item.get("prerequisite")
            if prerequisite is not None and prerequisite not in group_questions:
                raise LabValidationError(
                    f"Quiz prerequisite references an unknown item at /{group_id}/items/{item['id']}/prerequisite"
                )
            if prerequisite is not None:
                prerequisite_item = next(entry for entry in group_items if entry["id"] == prerequisite)
                if prerequisite_item.get("type", "choice") == "preface":
                    raise LabValidationError(
                        f"Quiz prerequisite must reference a question at /{group_id}/items/{item['id']}/prerequisite"
                    )
                if group_question_indexes[prerequisite] >= item_index:
                    raise LabValidationError(
                        f"Quiz prerequisite must reference an earlier question at /{group_id}/items/{item['id']}/prerequisite"
                    )
    return tuple(items)


class _LabYamlLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError("YAML aliases are not supported")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in mapping:
                raise yaml.YAMLError("Mapping keys must be unique strings")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def load_lab(path: str | Path) -> Lab:
    """Read and validate a local UTF-8 definition without runtime operations."""
    try:
        with Path(path).open("rb") as source:
            content = source.read(MAX_DEFINITION_BYTES + 1)
    except FileNotFoundError:
        raise LabReadError("Lab definition not found") from None
    except PermissionError:
        raise LabReadError("Permission denied reading Lab definition") from None
    except OSError:
        raise LabReadError("Cannot read Lab definition") from None

    if len(content) > MAX_DEFINITION_BYTES:
        raise LabValidationError("Lab definition exceeds the 1 MiB limit")
    try:
        document = yaml.load(content.decode("utf-8"), Loader=_LabYamlLoader)
    except (UnicodeError, yaml.YAMLError, RecursionError, ValueError):
        raise LabValidationError(
            "Invalid UTF-8 YAML: use one document with unique string keys, "
            "no aliases, merge keys, or custom tags"
        ) from None
    lab = validate_lab(document)
    try:
        return snapshot_documentation(snapshot_lab(lab, Path(path).parent), Path(path).parent)
    except AssetError as error:
        raise LabValidationError(str(error)) from None



def expand_clones(document: dict) -> dict:
    if not isinstance(document, dict) or "nodes" not in document or not isinstance(document["nodes"], list):
        return document

    has_clone = any(
        isinstance(node, dict) and (node.get("clone", 1) > 1 or any(
            isinstance(addr, str) and addr.upper().endswith("+CLONE")
            for addr in (node.get("addresses") or {}).values()
        ))
        for node in document["nodes"]
    )
    if not has_clone:
        return document

    expanded_doc = copy.deepcopy(document)
    new_nodes = []
    node_id_map = {}

    for node in expanded_doc["nodes"]:
        if not isinstance(node, dict) or "id" not in node:
            new_nodes.append(node)
            continue
        orig_id = node["id"]
        clone_count = node.get("clone", 1)
        if clone_count <= 1:
            if "addresses" in node and isinstance(node["addresses"], dict):
                cleaned_addrs = {}
                for net_id, addr in node["addresses"].items():
                    if isinstance(addr, str) and addr.upper().endswith("+CLONE"):
                        cleaned_addrs[net_id] = addr[:addr.upper().rfind("+CLONE")].strip()
                    else:
                        cleaned_addrs[net_id] = addr
                node["addresses"] = cleaned_addrs
            new_nodes.append(node)
            node_id_map[orig_id] = [orig_id]
            continue

        clone_ids = []
        for index in range(1, clone_count + 1):
            clone_node = copy.deepcopy(node)
            clone_id = f"{orig_id}-{index}"
            clone_ids.append(clone_id)
            clone_node["id"] = clone_id
            clone_node["clone"] = clone_count
            clone_node["clone_index"] = index
            if not clone_node.get("terminal_group"):
                clone_node["terminal_group"] = orig_id
            if clone_node.get("hostname"):
                clone_node["hostname"] = f"{clone_node['hostname']}-{index}"
            if "addresses" in clone_node and isinstance(clone_node["addresses"], dict):
                new_addrs = {}
                for net_id, addr in clone_node["addresses"].items():
                    if isinstance(addr, str) and addr.upper().endswith("+CLONE"):
                        base_ip_str = addr[:addr.upper().rfind("+CLONE")].strip()
                        try:
                            base_ip = IPv4Address(base_ip_str)
                        except ValueError:
                            raise LabValidationError(f"Invalid IPv4 address in +CLONE: {addr}")
                        new_addrs[net_id] = str(base_ip + (index - 1))
                    else:
                        new_addrs[net_id] = addr
                clone_node["addresses"] = new_addrs
            new_nodes.append(clone_node)
        node_id_map[orig_id] = clone_ids

    expanded_doc["nodes"] = new_nodes

    if "terminals" in expanded_doc and isinstance(expanded_doc["terminals"], list):
        new_terminals = []
        for term in expanded_doc["terminals"]:
            if term in node_id_map:
                new_terminals.extend(node_id_map[term])
            else:
                new_terminals.append(term)
        expanded_doc["terminals"] = new_terminals

    for node in expanded_doc["nodes"]:
        if isinstance(node, dict) and "wait_for" in node and isinstance(node["wait_for"], list):
            new_wf = []
            for wf in node["wait_for"]:
                if wf in node_id_map:
                    new_wf.extend(node_id_map[wf])
                else:
                    new_wf.append(wf)
            node["wait_for"] = new_wf

    settings = expanded_doc.get("settings", {})
    if isinstance(settings, dict) and settings.get("grade_node") in node_id_map:
        settings["grade_node"] = node_id_map[settings["grade_node"]][0]

    if "parameterizations" in expanded_doc and isinstance(expanded_doc["parameterizations"], list):
        new_params = []
        for op in expanded_doc["parameterizations"]:
            if not isinstance(op, dict) or "node" not in op:
                new_params.append(op)
                continue
            orig_node = op["node"]
            if orig_node in node_id_map and len(node_id_map[orig_node]) > 1:
                clone_ids = node_id_map[orig_node]
                op_copy = copy.deepcopy(op)
                orig_targets = op.get("targets")
                if orig_targets:
                    expanded_targets = []
                    for tgt in orig_targets:
                        tgt_node = tgt.get("node")
                        if tgt_node in node_id_map and len(node_id_map[tgt_node]) > 1:
                            for cid in node_id_map[tgt_node]:
                                expanded_targets.append({"node": cid, "path": tgt["path"]})
                        else:
                            expanded_targets.append(tgt)
                    op_copy["targets"] = expanded_targets
                    op_copy["node"] = clone_ids[0]
                else:
                    op_copy["node"] = clone_ids[0]
                    op_copy["targets"] = [{"node": cid, "path": op["path"]} for cid in clone_ids]
                new_params.append(op_copy)
            else:
                new_params.append(op)
        expanded_doc["parameterizations"] = new_params

    if "assessment" in expanded_doc and isinstance(expanded_doc["assessment"], dict):
        for art in expanded_doc["assessment"].get("artifacts", []):
            if isinstance(art, dict) and art.get("node") in node_id_map:
                art["node"] = node_id_map[art["node"]][0]
        for res in expanded_doc["assessment"].get("results", []):
            if isinstance(res, dict) and res.get("node") in node_id_map:
                res["node"] = node_id_map[res["node"]][0]

    return expanded_doc

def validate_lab(document: object) -> Lab:
    """Validate a parsed definition and return a detached, immutable model."""
    if isinstance(document, dict) and "apiVersion" in document:
        if document["apiVersion"] != API_VERSION:
            raise LabValidationError("Unsupported Lab apiVersion")

    schema = json.loads(
        files("cyberlab.schemas").joinpath("v1/lab.schema.json").read_text(
            encoding="utf-8"
        )
    )
    error = next(Draft202012Validator(schema).iter_errors(document), None)
    if error is not None:
        location = "/" + "/".join(str(part) for part in error.absolute_path)
        raise LabValidationError(
            f"Invalid Lab definition at {location}: {error.validator} constraint"
        )

    if isinstance(document, dict):
        document = expand_clones(document)

    for section in ("nodes", "networks"):
        identifiers = set()
        for index, item in enumerate(document[section]):
            if item["id"] in identifiers:
                raise LabValidationError(f"Duplicate identity at /{section}/{index}/id")
            identifiers.add(item["id"])

    network_ids = {network["id"] for network in document["networks"]}
    for node_index, node in enumerate(document["nodes"]):
        for network_index, network_id in enumerate(node["networks"]):
            if network_id not in network_ids:
                raise LabValidationError(
                    f"Undefined network at /nodes/{node_index}/networks/{network_index}"
                )

    node_ids = {node["id"] for node in document["nodes"]}
    try:
        validate_node_dependencies(document["nodes"])
    except ValueError as error:
        raise LabValidationError(str(error)) from None
    for index, node_id in enumerate(document.get("terminals", [])):
        if node_id not in node_ids:
            raise LabValidationError(f"Undefined terminal node at /terminals/{index}")

    settings = document.get("settings", {})
    if settings.get("grade_node") is not None and settings["grade_node"] not in node_ids:
        raise LabValidationError("Undefined grade node at /settings/grade_node")
    parameters = document.get("parameters", [])
    parameter_ids = set()
    for index, parameter in enumerate(parameters):
        if parameter["id"] in parameter_ids:
            raise LabValidationError(f"Duplicate parameter identity at /parameters/{index}/id")
        parameter_ids.add(parameter["id"])
        parameter_type = parameter["type"]
        choices = parameter.get("choices", [])
        default = parameter.get("default")
        if parameter_type == "choice" and not choices:
            raise LabValidationError(f"Choice parameter requires choices at /parameters/{index}")
        if parameter_type != "choice" and choices:
            raise LabValidationError(f"Only choice parameters may define choices at /parameters/{index}/choices")
        if default is not None:
            if parameter_type in {"text", "choice"} and not isinstance(default, str):
                raise LabValidationError(f"Parameter default type mismatch at /parameters/{index}/default")
            if parameter_type == "integer" and (isinstance(default, bool) or not isinstance(default, int)):
                raise LabValidationError(f"Parameter default type mismatch at /parameters/{index}/default")
            if parameter_type == "boolean" and not isinstance(default, bool):
                raise LabValidationError(f"Parameter default type mismatch at /parameters/{index}/default")
        if parameter_type == "choice" and default is not None and default not in choices:
            raise LabValidationError(f"Parameter default is not one of its choices at /parameters/{index}/default")

    operations = document.get("parameterizations", [])
    operation_ids = set()
    parameter_ids = {parameter["id"] for parameter in parameters}
    for index, operation in enumerate(operations):
        if operation["id"] in operation_ids:
            raise LabValidationError(f"Duplicate parameterization identity at /parameterizations/{index}/id")
        if operation["id"] in parameter_ids:
            raise LabValidationError(f"Parameter operation identity conflicts with parameter at /parameterizations/{index}/id")
        operation_ids.add(operation["id"])
        if operation["node"] not in node_ids:
            raise LabValidationError(f"Undefined parameterization node at /parameterizations/{index}/node")
        for target_index, target in enumerate(operation.get("targets", [])):
            if target.get("node") not in node_ids:
                raise LabValidationError(f"Undefined target node at /parameterizations/{index}/targets/{target_index}/node")
            if not isinstance(target.get("path"), str) or not WORKSPACE_PATH.fullmatch(target["path"]):
                raise LabValidationError(f"Unsafe target path at /parameterizations/{index}/targets/{target_index}/path")
        if operation["operation"] in {"rand_replace", "rand_replace_unique", "hash_replace", "clone_replace"} and not operation.get("token"):
            raise LabValidationError(f"{operation['operation']} requires token at /parameterizations/{index}/token")
        if operation["operation"] in {"rand_replace", "rand_replace_unique"}:
            if "value" in operation:
                raise LabValidationError(f"Random replacement does not accept a hash value at /parameterizations/{index}/value")
            lower, upper = operation.get("lower"), operation.get("upper")
            if lower is None or upper is None or lower > upper:
                raise LabValidationError(f"{operation['operation']} requires an ordered range at /parameterizations/{index}")
            if operation.get("step", 1) > upper - lower + 1:
                raise LabValidationError(f"{operation['operation']} step exceeds its range at /parameterizations/{index}")
        elif operation["operation"] == "clone_replace":
            if any(key in operation for key in ("lower", "upper", "step")):
                raise LabValidationError(f"clone_replace has random range fields at /parameterizations/{index}")
        elif any(key in operation for key in ("lower", "upper", "step")):
            raise LabValidationError(f"Hash operation has random range fields at /parameterizations/{index}")
        if operation["operation"] == "hash_create" and "token" in operation:
            raise LabValidationError(f"hash_create does not accept a replacement token at /parameterizations/{index}/token")

    assessment_document = document.get("assessment", {})
    artifacts = assessment_document.get("artifacts", [])
    results = assessment_document.get("results", [])
    goals = assessment_document.get("goals", [])
    assessment_ids = set()
    for collection_name, collection in (("artifacts", artifacts), ("results", results), ("goals", goals)):
        for index, item in enumerate(collection):
            if item["id"] in assessment_ids:
                raise LabValidationError(f"Duplicate assessment identity at /assessment/{collection_name}/{index}/id")
            assessment_ids.add(item["id"])
    result_ids = {item["id"] for item in results}
    for collection_name, collection in (("artifacts", artifacts), ("results", results)):
        for index, item in enumerate(collection):
            if item["node"] not in node_ids:
                raise LabValidationError(f"Undefined assessment node at /assessment/{collection_name}/{index}/node")
            if not WORKSPACE_PATH.fullmatch(item["path"]):
                raise LabValidationError(f"Unsafe assessment workspace path at /assessment/{collection_name}/{index}/path")
    for index, result in enumerate(results):
        operator = result["operator"]
        expected = result.get("expected")
        field_type = result.get("field_type")
        field_id = result.get("field_id")
        line_type = result.get("line_type")
        line_id = result.get("line_id")
        if operator != "exists" and expected is None:
            raise LabValidationError(f"Assessment result requires expected at /assessment/results/{index}/expected")
        if operator in {"size_less_than", "size_equals", "line_count_equals", "string_count_equals"} and (isinstance(expected, bool) or not isinstance(expected, int)):
            raise LabValidationError(f"{operator} requires an integer expected value at /assessment/results/{index}/expected")
        if operator == "sha256_equals" and (not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected)):
            raise LabValidationError(f"sha256_equals requires a SHA-256 hex value at /assessment/results/{index}/expected")
        if operator == "md5_equals" and (not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", expected)):
            raise LabValidationError(f"md5_equals requires an MD5 hex value at /assessment/results/{index}/expected")
        if operator not in {"size_less_than", "size_equals", "line_count_equals", "string_count_equals"} and expected is not None and not isinstance(expected, str):
            raise LabValidationError(f"Assessment result expected value must be text at /assessment/results/{index}/expected")
        if operator == "string_count_equals" and (not isinstance(result.get("field_id"), str) or not result["field_id"]):
            raise LabValidationError(f"string_count_equals requires a non-empty field_id at /assessment/results/{index}/field_id")
        if operator == "field_equals":
            if field_type is None or field_id is None or line_type is None or line_id is None:
                raise LabValidationError(f"field_equals requires field and line selectors at /assessment/results/{index}")
            if field_type == "group" and line_type != "regex":
                raise LabValidationError(f"group field requires a regex line selector at /assessment/results/{index}")
            if field_type == "group" and (isinstance(field_id, bool) or not isinstance(field_id, int) or not 0 <= field_id <= 32):
                raise LabValidationError(f"group field_id must be an integer at /assessment/results/{index}")
            if field_type != "group" and field_id not in {"ALL", "LAST"} and (isinstance(field_id, bool) or not isinstance(field_id, int) or field_id < 1):
                raise LabValidationError(f"field_id must be a positive integer, ALL or LAST at /assessment/results/{index}")
        elif any(value is not None for value in (field_type, line_type, line_id)) or (operator != "string_count_equals" and field_id is not None):
            raise LabValidationError(f"Field and line selectors are only valid with field_equals at /assessment/results/{index}")
        if line_type == "line" and (isinstance(line_id, bool) or not isinstance(line_id, int)):
            raise LabValidationError(f"line selector requires an integer line_id at /assessment/results/{index}")
        if line_type != "line" and line_id is not None and not isinstance(line_id, str):
            raise LabValidationError(f"line selector requires text line_id at /assessment/results/{index}")
    previous_goal_ids = set()
    boolean_references = {}
    for index, goal in enumerate(goals):
        for result_index, result_id in enumerate(goal.get("results", [])):
            if result_id not in result_ids and result_id not in previous_goal_ids:
                raise LabValidationError(f"Undefined result in goal at /assessment/goals/{index}/results/{result_index}")
        goal_type = goal.get("type", "group")
        if goal_type not in {"compare", "boolean"} and not goal.get("results"):
            raise LabValidationError(f"Goal requires results at /assessment/goals/{index}/results")
        if goal_type == "group":
            if any(key in goal for key in ("operator", "result", "other", "expected", "threshold", "expression")):
                raise LabValidationError(f"Group goal has comparison fields at /assessment/goals/{index}")
        elif goal_type == "compare":
            if any(key in goal for key in ("mode", "threshold", "expression")):
                raise LabValidationError(f"Compare goal has group or count fields at /assessment/goals/{index}")
            if goal.get("result") not in result_ids:
                raise LabValidationError(f"Compare goal references an undefined result at /assessment/goals/{index}/result")
            if goal.get("operator") not in COMPARE_OPERATORS:
                raise LabValidationError(f"Compare goal requires a comparison operator at /assessment/goals/{index}/operator")
            if goal.get("other") is None and goal.get("expected") is None:
                raise LabValidationError(f"Compare goal requires other or expected at /assessment/goals/{index}")
            if goal.get("other") is not None and goal["other"] not in result_ids:
                raise LabValidationError(f"Compare goal references an undefined other result at /assessment/goals/{index}/other")
            if goal.get("other") is not None and goal.get("expected") is not None:
                raise LabValidationError(f"Compare goal cannot define both other and expected at /assessment/goals/{index}")
            references = {goal["result"]} | ({goal["other"]} if "other" in goal else set())
            if "results" in goal and set(goal["results"]) != references:
                raise LabValidationError(f"Compare goal results must match its operands at /assessment/goals/{index}/results")
            expected = goal.get("expected")
            if goal["operator"] in INTEGER_OPERATORS and expected is not None and not (
                    isinstance(expected, str) and PARAMETER_TOKEN.search(expected)):
                try:
                    integer_value(expected)
                except ValueError as error:
                    raise LabValidationError(f"{error} at /assessment/goals/{index}/expected") from None
            if goal["operator"] in HASH_OPERATORS and expected is not None and not (
                    isinstance(expected, str) and PARAMETER_TOKEN.search(expected)):
                if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{32}|[0-9a-fA-F]{64}", expected.strip()):
                    raise LabValidationError(f"hash_equal requires a 32 or 64 hex character digest at /assessment/goals/{index}/expected")
        elif goal_type == "count":
            if any(key in goal for key in ("mode", "result", "other", "expected", "expression")):
                raise LabValidationError(f"Count goal has comparison or group fields at /assessment/goals/{index}")
            if goal.get("operator") != "count_greater" or type(goal.get("threshold")) is not int:
                raise LabValidationError(f"Count goal requires count_greater and threshold at /assessment/goals/{index}")
        elif goal_type == "boolean":
            if any(key in goal for key in ("mode", "operator", "result", "other", "expected", "threshold")):
                raise LabValidationError(f"Boolean goal has comparison or group fields at /assessment/goals/{index}")
            expr = goal.get("expression")
            if not expr or not isinstance(expr, str) or not expr.strip():
                raise LabValidationError(f"Boolean goal requires expression at /assessment/goals/{index}/expression")
            cleaned = re.sub(r"\band_not\b", "and not", expr, flags=re.I)
            cleaned = re.sub(r"\bor_not\b", "or not", cleaned, flags=re.I)
            tokens = re.findall(r"\(|\)|\b(?:and|or|not|true|false)\b|[a-z0-9][a-z0-9_-]*", cleaned, re.I)
            stripped = re.sub(r"\s+", "", cleaned)
            if stripped.lower() != "".join(tokens).lower():
                raise LabValidationError(f"Invalid character in boolean expression at /assessment/goals/{index}/expression")
            referenced = []
            for token in tokens:
                low = token.lower()
                if low not in {"(", ")", "and", "or", "not", "true", "false"}:
                    if low not in result_ids and low not in previous_goal_ids:
                        raise LabValidationError(f"Undefined result or goal '{token}' in boolean expression at /assessment/goals/{index}/expression")
                    if low not in referenced:
                        referenced.append(low)
            try:
                evaluate_boolean_expression(cleaned, {ident: True for ident in referenced})
            except Exception as error:
                raise LabValidationError(f"Invalid boolean expression syntax ({error}) at /assessment/goals/{index}/expression") from None
            if "results" in goal and set(goal["results"]) != set(referenced):
                raise LabValidationError(f"Boolean goal results must match its expression operands at /assessment/goals/{index}/results")
            boolean_references[index] = tuple(referenced)
        else:
            raise LabValidationError(f"Unsupported goal type at /assessment/goals/{index}/type")
        previous_goal_ids.add(goal["id"])

    quiz = _quiz_items(document)

    documentation = Documentation(document["documentation"]) if "documentation" in document else None
    try:
        validate_documentation(documentation)
    except AssetError as error:
        raise LabValidationError(str(error)) from None

    for node in document["nodes"]:
        try:
            hostname = node.get("hostname")
            if hostname:
                hostname = PARAMETER_TOKEN.sub("param", hostname)
            validate_environment(hostname, NodeUser(**node["user"]) if "user" in node else None)
            validate_mappings(tuple(FileMapping(**mapping) for mapping in node.get("files", [])))
        except (AssetError, ValueError) as error:
            raise LabValidationError(str(error)) from None

    lab = Lab(
        api_version=document["apiVersion"],
        metadata=LabMetadata(**document["metadata"]),
        nodes=tuple(
            Node(
                id=node["id"], networks=tuple(node["networks"]),
                image=node.get("image"), command=tuple(node.get("command", [])),
                files=tuple(FileMapping(**mapping) for mapping in node.get("files", [])),
                hostname=node.get("hostname"),
                user=NodeUser(**node["user"]) if "user" in node else None,
                addresses=tuple(sorted(node.get("addresses", {}).items())),
                dns=tuple(node.get("dns", [])), terminal_count=node.get("terminal_count", 1),
                terminal_group=node.get("terminal_group"), terminal_title=node.get("terminal_title"),
                aliases=tuple(node.get("aliases", [])), wait_for=tuple(node.get("wait_for", [])),
                resources=NodeResources(**node.get("resources", {})),
                extra_hosts=tuple(sorted(node.get("extra_hosts", {}).items())),
                clone=node.get("clone", 1),
                clone_index=node.get("clone_index"),
            )
            for node in document["nodes"]
        ),
        networks=tuple(Network(**network) for network in document["networks"]),
        terminals=tuple(document.get("terminals", [])),
        documentation=documentation,
        settings=LabSettings(
            master_seed=settings.get("master_seed"),
            host_home_xfer=settings.get("host_home_xfer"),
            grade_node=settings.get("grade_node"),
            collect_documentation=settings.get("collect_documentation", False),
            checkwork=settings.get("checkwork", False),
        ),
        parameters=tuple(
            Parameter(
                id=parameter["id"], type=parameter["type"], default=parameter.get("default"),
                choices=tuple(parameter.get("choices", [])), description=parameter.get("description", ""),
                public=parameter.get("public", True),
            )
            for parameter in parameters
        ),
        parameter_operations=tuple(
            ParameterOperation(
                id=operation["id"], operation=operation["operation"], node=operation["node"],
                path=operation["path"], token=operation.get("token", ""), value=operation.get("value", ""),
                lower=operation.get("lower", 0), upper=operation.get("upper", 0), step=operation.get("step", 1),
                targets=tuple((target["node"], target["path"]) for target in operation.get("targets", [])),
            )
            for operation in operations
        ),
        assessment=Assessment(
            artifacts=tuple(
                AssessmentArtifact(
                    id=artifact["id"], node=artifact["node"], path=artifact["path"],
                    label=artifact.get("label", ""), required=artifact.get("required", True),
                )
                for artifact in artifacts
            ),
            results=tuple(
                AssessmentResult(
                    id=result["id"], node=result["node"], path=result["path"], operator=result["operator"],
                    expected=result.get("expected"), description=result.get("description", ""),
                    hint=result.get("hint", ""),
                    field_type=result.get("field_type"), field_id=result.get("field_id"),
                    line_type=result.get("line_type"), line_id=result.get("line_id"),
                )
                for result in results
            ),
            goals=tuple(
                AssessmentGoal(
                    id=goal["id"],
                    results=(tuple(dict.fromkeys([goal["result"]] + ([goal["other"]] if "other" in goal else [])))
                             if goal.get("type") == "compare"
                             else boolean_references.get(index, ())
                             if goal.get("type") == "boolean"
                             else tuple(goal["results"])),
                    mode=goal.get("mode", "all"),
                    description=goal.get("description", ""), goal_type=goal.get("type", "group"),
                    operator=goal.get("operator", ""), result=goal.get("result", ""),
                    other=goal.get("other", ""), expected=goal.get("expected"),
                    threshold=goal.get("threshold"),
                    expression=goal.get("expression", ""),
                )
                for index, goal in enumerate(goals)
            ),
        ),
        quiz=quiz,
    )
    from cyberlab.parameter_operations import validate_operations
    try:
        validate_operations(lab)
        eval_lab = lab
        has_params = any(PARAMETER_TOKEN.search(addr) for node in lab.nodes for _, addr in node.addresses) or any(
            net.subnet and PARAMETER_TOKEN.search(net.subnet) for net in lab.networks
        ) or any(
            net.gateway and PARAMETER_TOKEN.search(net.gateway) for net in lab.networks
        )
        if has_params:
            defaults = {p.id: p.default for p in lab.parameters if p.default is not None}
            def sub_param(text):
                if not isinstance(text, str):
                    return text
                def repl(match):
                    token = match.group(0)
                    m = re.search(r"param:([a-z0-9_-]+)", token, re.I)
                    name = m.group(1) if m else token
                    if name in defaults:
                        return str(defaults[name])
                    return token
                return PARAMETER_TOKEN.sub(repl, text)

            eval_nodes = tuple(
                replace(n, addresses=tuple((net, sub_param(addr)) for net, addr in n.addresses))
                for n in lab.nodes
            )
            eval_networks = tuple(
                replace(net, subnet=sub_param(net.subnet) if net.subnet else None,
                             gateway=sub_param(net.gateway) if net.gateway else None)
                for net in lab.networks
            )
            eval_lab = replace(lab, nodes=eval_nodes, networks=eval_networks)
        validate_networking(eval_lab)
    except ValueError as error:
        raise LabValidationError(str(error)) from None
    return lab
