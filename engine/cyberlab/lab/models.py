from dataclasses import dataclass


@dataclass(frozen=True)
class LabMetadata:
    id: str
    name: str
    version: str


@dataclass(frozen=True)
class FileMapping:
    source: str
    target: str

@dataclass(frozen=True)
class SeedEntry:
    path: str
    data: bytes | None = None

@dataclass(frozen=True)
class NodeUser:
    name: str
    uid: int
    gid: int
    home: str
    shell: str

@dataclass(frozen=True)
class NodeResources:
    memory_mb: int = 128
    cpu_millicores: int = 500

@dataclass(frozen=True)
class Node:
    id: str
    networks: tuple[str, ...]
    image: str | None = None
    command: tuple[str, ...] = ()
    files: tuple[FileMapping, ...] = ()
    seed: tuple[SeedEntry, ...] = ()
    hostname: str | None = None
    user: NodeUser | None = None
    addresses: tuple[tuple[str, str], ...] = ()
    dns: tuple[str, ...] = ()
    terminal_count: int = 1
    terminal_group: str | None = None
    terminal_title: str | None = None
    aliases: tuple[str, ...] = ()
    wait_for: tuple[str, ...] = ()
    resources: NodeResources = NodeResources()
    extra_hosts: tuple[tuple[str, str], ...] = ()
    clone: int = 1
    clone_index: int | None = None


@dataclass(frozen=True)
class Network:
    id: str
    subnet: str | None = None
    gateway: str | None = None


@dataclass(frozen=True)
class Documentation:
    source: str
    content: str | None = None

@dataclass(frozen=True)
class LabSettings:
    master_seed: str | None = None
    host_home_xfer: str | None = None
    grade_node: str | None = None
    collect_documentation: bool = False
    checkwork: bool = False

@dataclass(frozen=True)
class Parameter:
    id: str
    type: str
    default: str | int | bool | None = None
    choices: tuple[str, ...] = ()
    description: str = ""
    public: bool = True

@dataclass(frozen=True)
class ParameterOperation:
    id: str
    operation: str
    node: str
    path: str
    token: str = ""
    value: str = ""
    lower: int = 0
    upper: int = 0
    step: int = 1
    targets: tuple[tuple[str, str], ...] = ()

@dataclass(frozen=True)
class AssessmentArtifact:
    id: str
    node: str
    path: str
    label: str = ""
    required: bool = True

@dataclass(frozen=True)
class AssessmentResult:
    id: str
    node: str
    path: str
    operator: str
    expected: str | int | None = None
    description: str = ""
    hint: str = ""
    field_type: str | None = None
    field_id: str | int | None = None
    line_type: str | None = None
    line_id: str | int | None = None

@dataclass(frozen=True)
class AssessmentGoal:
    id: str
    results: tuple[str, ...]
    mode: str = "all"
    description: str = ""
    goal_type: str = "group"
    operator: str = ""
    result: str = ""
    other: str = ""
    expected: str | int | None = None
    threshold: int | None = None
    expression: str = ""

@dataclass(frozen=True)
class Assessment:
    artifacts: tuple[AssessmentArtifact, ...] = ()
    results: tuple[AssessmentResult, ...] = ()
    goals: tuple[AssessmentGoal, ...] = ()

@dataclass(frozen=True)
class QuizQuestion:
    id: str
    question: str
    options: tuple[str, ...]
    answer: int | None = None
    explanation: str = ""
    item_type: str = "choice"
    text: str = ""
    right_response: str = ""
    wrong_response: str = ""
    prerequisite: str | None = None
    quiz_id: str = "default"
    quiz_title: str = ""
    pre_start: bool = False

@dataclass(frozen=True)
class Lab:
    api_version: str
    metadata: LabMetadata
    nodes: tuple[Node, ...]
    networks: tuple[Network, ...]
    terminals: tuple[str, ...] = ()
    documentation: Documentation | None = None
    settings: LabSettings = LabSettings()
    parameters: tuple[Parameter, ...] = ()
    parameter_operations: tuple[ParameterOperation, ...] = ()
    assessment: Assessment = Assessment()
    quiz: tuple[QuizQuestion, ...] = ()
