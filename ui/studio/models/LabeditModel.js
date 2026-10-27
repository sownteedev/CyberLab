.pragma library
.import "AssessmentModel.js" as Assessment

function assessmentEntries(document) {
    const assessment = document.assessment || {};
    return (assessment.artifacts || []).concat(assessment.results || [], assessment.goals || []);
}

function renameNode(document, previous, replacement) {
    document.nodes.forEach(node => {
        if (node.wait_for) node.wait_for = node.wait_for.map(value => value === previous ? replacement : value);
    });
    assessmentEntries(document).forEach(entry => { if (entry.node === previous) entry.node = replacement; });
    (document.parameterizations || []).forEach(entry => { if (entry.node === previous) entry.node = replacement; });
    if (document.settings && document.settings.grade_node === previous) document.settings.grade_node = replacement;
}

function requireUnusedNode(document, identifier) {
    if (assessmentEntries(document).some(entry => entry.node === identifier)
            || (document.parameterizations || []).some(entry => entry.node === identifier)
            || document.nodes.some(node => (node.wait_for || []).includes(identifier))
            || (document.settings && document.settings.grade_node === identifier))
        throw new Error("Máy đang được tham chiếu trong điều kiện, bằng chứng hoặc thứ tự khởi động.");
}

function rewriteTokens(value, previous, replacement) {
    if (typeof value === "string") return value.split("{{param:" + previous + "}}").join("{{param:" + replacement + "}}")
        .split("${PARAM:" + previous + "}").join("${PARAM:" + replacement + "}");
    if (Array.isArray(value)) {
        value.forEach((item, index) => { value[index] = rewriteTokens(item, previous, replacement); });
        return value;
    }
    if (value && typeof value === "object") Object.keys(value).forEach(key => {
        value[key] = rewriteTokens(value[key], previous, replacement);
    });
    return value;
}

function requireUnusedParameter(document, identifier) {
    const serialized = JSON.stringify(document);
    if (serialized.includes("{{param:" + identifier + "}}") || serialized.includes("${PARAM:" + identifier + "}"))
        throw new Error("Tham số đang được dùng trong cấu hình. Bỏ tham chiếu trước khi xóa.");
}

function parameterValue(parameter, value) {
    if (value === null || value === undefined) return null;
    if (parameter.type === "integer") {
        if (!/^-?[0-9]+$/.test(String(value)) || !Number.isSafeInteger(Number(value))
                || Number(value) < -2147483648 || Number(value) > 2147483647)
            throw new Error("Giá trị mặc định phải là số nguyên 32-bit.");
        return Number(value);
    }
    if (parameter.type === "boolean") {
        if (value === true || value === "true") return true;
        if (value === false || value === "false") return false;
        throw new Error("Giá trị phải là true hoặc false.");
    }
    if (parameter.type === "choice" && !(parameter.choices || []).includes(value))
        throw new Error("Chọn một giá trị trong danh sách đã khai báo.");
    return String(value);
}

function renameResult(document, previous, replacement) {
    ((document.assessment || {}).goals || []).forEach(goal => {
        if (goal.results) goal.results = goal.results.map(identifier => identifier === previous ? replacement : identifier);
        if (goal.result === previous) goal.result = replacement;
        if (goal.other === previous) goal.other = replacement;
        if (goal.expression) {
            const re = new RegExp("\\b" + previous + "\\b", "g");
            goal.expression = goal.expression.replace(re, replacement);
        }
    });
}

function renameGoal(document, previous, replacement) {
    ((document.assessment || {}).goals || []).forEach(goal => {
        if (goal.expression) {
            const re = new RegExp("\\b" + previous + "\\b", "g");
            goal.expression = goal.expression.replace(re, replacement);
        }
    });
}

function requireUnusedResult(document, identifier) {
    if (((document.assessment || {}).goals || []).some(goal => Assessment.references(goal).includes(identifier)))
        throw new Error("Điều kiện đang được dùng trong mục tiêu. Bỏ chọn trong mục tiêu trước khi xóa.");
}

function requireUnusedGoal(document, identifier) {
    if (((document.assessment || {}).goals || []).some(goal => goal.type === "boolean" && Assessment.references(goal).includes(identifier)))
        throw new Error("Mục tiêu đang được dùng trong biểu thức của mục tiêu khác. Bỏ tham chiếu trước khi xóa.");
}

function updateOperation(entry, field, value) {
    if (field === "operation" && value !== entry.operation) {
        ["lower", "upper", "step"].forEach(key => { delete entry[key]; });
        if (value === "rand_replace" || value === "rand_replace_unique") {
            delete entry.value;
            Object.assign(entry, {lower: 1, upper: 100, step: 1});
        } else if (value === "clone_replace") {
            delete entry.value;
            if (!entry.token) entry.token = "TOKEN";
        } else if (entry.value === undefined) entry.value = "";
        if (value === "hash_create") delete entry.token;
        else if (!entry.token) entry.token = "TOKEN";
    }
    if (["lower", "upper", "step"].includes(field)) value = Assessment.boundedInteger(value, field === "step" ? 1 : 0, 2147483647);
    Assessment.assign(entry, field, value);
}
