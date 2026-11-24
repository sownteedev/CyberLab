import {render} from "./CodeSyntax.mjs";

WorkerScript.onMessage = function(message) {
    WorkerScript.sendMessage({text: message.text, language: message.language, dark: message.dark,
        markup: render(message.text, message.language, message.dark)});
};
