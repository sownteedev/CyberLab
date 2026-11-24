import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio

Item {
    id: checks

    property string screenshotFolder: ""

    ApplicationWindow {
        id: window
        width: 1000
        height: 700
        visible: true
        color: Studio.Theme.surface

        Studio.StudioViewport {
            hostWindow: window

            Studio.MarkdownView {
                id: preview
                anchors.fill: parent
                anchors.margins: 20
            }
        }

        TestCase {
            name: "MarkdownScrolling"
            when: window.visible

            function test_round_trip_data() {
                return [
                    {tag: "paragraphs", tables: false, width: 1000, theme: "dark", zoom: 100},
                    {tag: "tables", tables: true, width: 1000, theme: "dark", zoom: 100},
                    {tag: "tables-light", tables: true, width: 1000, theme: "light", zoom: 100},
                    {tag: "tables-narrow", tables: true, width: 380, theme: "dark", zoom: 100},
                    {tag: "tables-zoom70", tables: true, width: 1000, theme: "light", zoom: 70},
                    {tag: "tables-zoom150", tables: true, width: 1000, theme: "dark", zoom: 150}
                ];
            }

            function test_round_trip(data) {
                window.width = data.width;
                Studio.Theme.themeMode = data.theme;
                Studio.Theme.setZoomPercent(data.zoom);
                preview.markdown = Array.from({length: 24}, (_, index) =>
                    "## Section " + index + "\n\n"
                    + "Read the instructions and inspect the packets exchanged by the two machines.\n\n"
                    + "```sh\nping -c 3 10.242.71.20\ncurl http://10.242.71.20:8080/hello.txt\n```\n\n"
                    + (data.tables ? "| Filter | Observe |\n| --- | --- |\n| arp | Request and reply |\n| icmp | Echo request and reply |\n\n" : "")
                ).join("\n");
                const scroll = preview.contentItem;
                wait(100);
                tryVerify(() => scroll.contentHeight > scroll.height * 4);
                const document = findChild(preview, "documentText");
                document.select(0, 9);
                const selected = document.selectedText;
                verify(selected.length > 0);
                const checkpoints = [0, 0.15, 0.4, 0.7];
                const snapshots = checkpoints.map(fraction => {
                    scroll.contentY = fraction * (scroll.contentHeight - scroll.height);
                    wait(100);
                    return grabImage(preview);
                });
                for (let position = 0; position < scroll.contentHeight - scroll.height; position += 250) {
                    scroll.contentY = position;
                    wait(16);
                }
                for (let position = scroll.contentHeight - scroll.height; position > 0; position -= 250) {
                    scroll.contentY = position;
                    wait(16);
                }
                for (let index = 0; index < checkpoints.length; index++) {
                    scroll.contentY = checkpoints[index] * (scroll.contentHeight - scroll.height);
                    wait(100);
                    const returned = grabImage(preview);
                    if (checks.screenshotFolder) {
                        snapshots[index].save(checks.screenshotFolder + "/markdown-" + data.tag + "-" + index + "-before.png");
                        returned.save(checks.screenshotFolder + "/markdown-" + data.tag + "-" + index + "-after.png");
                    }
                    verify(snapshots[index].equals(returned), "Document must remain painted at checkpoint " + index);
                }
                compare(document.selectedText, selected);
                document.deselect();
            }
        }
    }
}
