.pragma library

function boundedInteger(value, minimum, maximum) {
    const text = String(value).trim();
    const number = Number(text);
    if (!/^[0-9]+$/.test(text) || !Number.isSafeInteger(number) || number < minimum || number > maximum)
        throw new Error("Giá trị phải là số nguyên từ " + minimum + " đến " + maximum + ".");
    return number;
}

function assign(entry, field, value) {
    if (value === null || value === undefined) delete entry[field];
    else entry[field] = value;
}

function updateCollection(entry, field, value) {
    const selectors = ["token", "parens", "quotes", "slash", "group", "search"];
    const textFields = ["contains", "file_regex", "string_count", "command_count", "search"];
    if (field === "field_type" && value !== entry.field_type) {
        ["field_id", "line_type", "line_id", "timestamp_type"].forEach(key => { delete entry[key]; });
        if (selectors.includes(value)) Object.assign(entry, {line_type: "none", field_id: 1});
        if (textFields.includes(value)) entry.field_id = value === "search" ? "value={:d}" : "";
        if (value === "param") entry.field_id = 1;
        if (value === "group") Object.assign(entry, {line_type: "regex", line_id: "^(.*)$", field_id: 1});
    }
    if (field === "line_type" && value !== entry.line_type) {
        if (value === "none") delete entry.line_id;
        else entry.line_id = value === "line" ? 1 : "";
        if (entry.field_type === "group" && value !== "regex") Object.assign(entry, {field_type: "token", field_id: 1});
        if (["line", "previous_starts_with"].includes(value)) delete entry.timestamp_type;
    }
    if (field === "timestamp_type" && value !== "file" && ["line", "previous_starts_with"].includes(entry.line_type)) {
        entry.line_type = "none";
        delete entry.line_id;
    }
    if (field === "line_id" && entry.line_type === "line") value = boundedInteger(value, 1, 1048576);
    if (field === "field_id" && !textFields.includes(entry.field_type)) {
        value = String(value).trim();
        if (entry.field_type === "group") value = boundedInteger(value, 0, 32);
        else if (entry.field_type === "param") value = boundedInteger(value, 0, 4096);
        else if (!["ALL", "LAST"].includes(value)) value = boundedInteger(value, 1, 4096);
    }
    assign(entry, field, value);
}

function updateResult(entry, field, value) {
    if (entry.operator === "collect" && field !== "operator") {
        updateCollection(entry, field, value);
        return;
    }
    const numeric = ["size_less_than", "size_equals", "line_count_equals", "string_count_equals"];
    if (field === "operator" && value !== entry.operator) {
        ["expected", "field_type", "field_id", "line_type", "line_id", "timestamp_type"].forEach(key => { delete entry[key]; });
        if (!["exists", "extract", "collect"].includes(value)) entry.expected = numeric.includes(value) ? 0 : "";
        if (value === "collect") Object.assign(entry, {field_type: "token", field_id: "ALL", line_type: "none"});
        if (["field_equals", "extract"].includes(value)) Object.assign(entry, {field_type: "token", field_id: 1, line_type: "line", line_id: 1});
        if (value === "string_count_equals") entry.field_id = "";
    }
    if (field === "expected") {
        if (numeric.includes(entry.operator)) value = boundedInteger(value, 0, 16777216);
        if (entry.operator === "sha256_equals" && !/^[0-9a-fA-F]{64}$/.test(String(value)))
            throw new Error("SHA-256 phải gồm đúng 64 ký tự hex.");
        if (entry.operator === "md5_equals" && !/^[0-9a-fA-F]{32}$/.test(String(value)))
            throw new Error("MD5 phải gồm đúng 32 ký tự hex.");
    }
    if (field === "field_type" && value !== entry.field_type) {
        entry.field_id = value === "group" ? 0 : 1;
        if (value === "group" && entry.line_type !== "regex") {
            entry.line_type = "regex";
            entry.line_id = "^(.*)$";
        }
    }
    if (field === "line_type" && value !== entry.line_type) {
        if (value === "line") entry.line_id = 1;
        else if (entry.line_type === "line") entry.line_id = "";
        if (entry.field_type === "group" && value !== "regex") {
            entry.field_type = "token";
            entry.field_id = 1;
        }
    }
    if (field === "line_id" && entry.line_type === "line") value = boundedInteger(value, 1, 1048576);
    if (field === "field_id" && ["field_equals", "extract"].includes(entry.operator)) {
        value = String(value).trim();
        if (entry.field_type === "group") value = boundedInteger(value, 0, 32);
        else if (!["ALL", "LAST"].includes(value)) value = boundedInteger(value, 1, 4096);
    }
    assign(entry, field, value);
}

function references(goal) {
    if (goal.type === "compare")
        return [goal.result, goal.other].filter((value, index, values) => value && values.indexOf(value) === index);
    if (goal.type === "boolean") {
        if (!goal.expression) return [];
        const matches = (goal.expression.match(/[a-zA-Z0-9_-]+/g) || [])
            .filter(token => !["and", "or", "not", "and_not", "or_not", "true", "false"].includes(token.toLowerCase()));
        return Array.from(new Set(matches));
    }
    return goal.results || [];
}

function updateGoal(entry, field, value, results) {
    if (field === "type" && value !== (entry.type || "group")) {
        const selected = references(entry);
        if (!selected.length && results.length) selected.push(results[0].id);
        ["results", "mode", "operator", "result", "other", "expected", "threshold", "expression"].forEach(key => { delete entry[key]; });
        if (value === "compare") Object.assign(entry, {result: selected[0] || "", operator: "string_equal", expected: ""});
        else if (value === "boolean") Object.assign(entry, {expression: selected[0] || ""});
        else {
            entry.results = selected;
            if (value === "count") Object.assign(entry, {operator: "count_greater", threshold: 0});
            else entry.mode = "all";
        }
    }
    if (field === "other") {
        if (value) delete entry.expected;
        else if (entry.expected === undefined) entry.expected = "";
    }
    if (field === "expected") {
        delete entry.other;
        if (entry.operator === "hash_equal" && value && !/^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{64}$/.test(String(value).trim()))
            throw new Error("Mã băm phải gồm 32 (MD5) hoặc 64 (SHA-256) ký tự hex.");
    }
    if (field === "operator" && value === "hash_equal") {
        delete entry.other;
        if (entry.expected === undefined) entry.expected = "";
    }
    if (field === "threshold") value = boundedInteger(value, 0, 64);
    assign(entry, field, value);
    if (entry.type === "compare" || entry.type === "boolean") delete entry.results;
}
