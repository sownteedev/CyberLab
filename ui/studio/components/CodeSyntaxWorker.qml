import QtQuick
import QtQml.WorkerScript

Item {
    id: worker
    required property string text
    required property string language
    required property bool dark
    property string markup: ""
    property bool busy: false

    function schedule() {
        markup = "";
        debounce.restart();
    }
    onTextChanged: schedule()
    onLanguageChanged: schedule()
    onDarkChanged: schedule()
    Component.onCompleted: schedule()

    Timer {
        id: debounce
        interval: worker.text.length > 8192 ? 80 : 1
        onTriggered: {
            if (!script.ready || worker.busy) return;
            worker.busy = true;
            script.sendMessage({text: worker.text, language: worker.language, dark: worker.dark});
        }
    }
    WorkerScript {
        id: script
        source: "../models/CodeSyntaxWorker.mjs"
        onReadyChanged: if (ready) debounce.restart()
        onMessage: message => {
            worker.busy = false;
            if (message.text === worker.text && message.language === worker.language && message.dark === worker.dark)
                worker.markup = message.markup;
            else debounce.restart();
        }
    }
}
