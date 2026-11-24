import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio
import "../models/FilePickerPaths.js" as Paths

Item {
    id: checks
    required property url fixtureFolder
    property string screenshotFolder: ""
    property bool confirmAfterAccept: false

    ApplicationWindow {
        id: window
        width: 1000
        height: 760
        visible: true
        color: Studio.Theme.surface

        Button { id: caller; text: "Open" }
        Studio.StudioFileDialog {
            id: picker
            title: "Nhập gói vào bản nháp"
            onAccepted: if (checks.confirmAfterAccept) confirmation.open()
        }
        Studio.ConfirmDialog { id: confirmation; title: "Xác nhận"; message: "Temporary confirmation"; danger: true }
        Studio.StudioFolderDialog { id: folderPicker; currentFolder: checks.fixtureFolder }
        SignalSpy { id: accepted; target: picker; signalName: "accepted" }
        SignalSpy { id: rejected; target: picker; signalName: "rejected" }
        SignalSpy { id: errors; target: Studio.StudioFeedback; signalName: "errorRequested" }
        TestCase {
            name: "StudioFilePicker"
            when: window.visible

            function file(name) { return Paths.destination(checks.fixtureFolder, name, ""); }
            function ready() { tryCompare(picker, "loading", false); tryCompare(picker, "validFolder", true); }
            function select(name) { picker.selectEntry(file(name), false, name); }
            function viewIndex(name) { return picker.folderModel.indexOf(file(name)) - picker.dotCount; }
            function init() {
                Studio.Theme.reducedMotion = true;
                Studio.Theme.themeMode = "dark";
                window.width = 1000;
                window.height = 760;
                picker.fileMode = "open";
                picker.folderOnly = false;
                picker.selectedFile = "";
                picker.selectedFiles = [];
                picker.selectedFolder = "";
                picker.fileName = "";
                picker.defaultSuffix = "";
                picker.filterIndex = 0;
                picker.showHidden = false;
                picker.nameFilters = ["Gói bài lab (*.cyberlab)", "Tất cả file (*.*)"];
                picker.currentFolder = checks.fixtureFolder;
                accepted.clear();
                rejected.clear();
                checks.confirmAfterAccept = false;
                window.requestActivate();
                tryCompare(window, "active", true);
                caller.forceActiveFocus();
                tryCompare(caller, "activeFocus", true);
                picker.open();
                tryCompare(picker, "opened", true);
                ready();
            }
            function cleanup() {
                confirmation.close();
                picker.reject();
                tryCompare(picker, "visible", false);
            }
            function test_single_click_accept() {
                const index = viewIndex("mang-co-ban.cyberlab");
                verify(index >= 0);
                const list = findChild(window, "filePickerEntries");
                tryVerify(() => list.itemAtIndex(index) !== null);
                const entry = list.itemAtIndex(index);
                verify(entry.width >= 120 && entry.height >= 120);
                mouseClick(entry);
                compare(picker.selection.length, 1);
                const preview = findChild(window, "filePickerPreview");
                verify(preview);
                compare(preview.fileName, "mang-co-ban.cyberlab");
                compare(preview.directory, false);
                mouseClick(findChild(window, "filePickerAccept"));
                compare(accepted.count, 1);
                compare(Paths.localPath(picker.selectedFile), Paths.localPath(file("mang-co-ban.cyberlab")));
            }
            function test_cancel_and_focus() {
                select("mang-co-ban.cyberlab");
                keyClick(Qt.Key_Escape);
                tryCompare(picker, "visible", false);
                compare(accepted.count, 0);
                compare(rejected.count, 1);
                compare(String(picker.selectedFile), "");
                tryCompare(caller, "activeFocus", true);
            }
            function test_confirmation_keeps_focus() {
                checks.confirmAfterAccept = true;
                select("mang-co-ban.cyberlab");
                picker.choose();
                tryCompare(confirmation, "opened", true);
                wait(50);
                compare(window.activeFocusItem.objectName, "confirmCancelButton");
            }
            function test_multiple_keyboard() {
                picker.fileMode = "openMany";
                const list = findChild(window, "filePickerEntries");
                list.forceActiveFocus();
                keyClick(Qt.Key_Home);
                compare(list.currentIndex, 0);
                keyClick(Qt.Key_Up);
                compare(list.currentIndex, 0);
                list.currentIndex = viewIndex("mang-co-ban.cyberlab");
                keyClick(Qt.Key_Space);
                list.currentIndex = viewIndex("Mạng #1 % thử.cyberlab");
                keyClick(Qt.Key_Space);
                compare(picker.selection.length, 2);
                picker.choose();
                compare(accepted.count, 1);
                compare(picker.selectedFiles.length, 2);
            }
            function test_grid_has_no_dot_gaps_and_counts_entries() {
                const grid = findChild(window, "filePickerEntries");
                tryCompare(grid, "count", picker.entryCount);
                const countLabel = findChild(window, "filePickerCount");
                compare(countLabel.text, picker.entryCount + " mục");
                tryVerify(() => grid.itemAtIndex(0) !== null);
                const first = grid.itemAtIndex(0);
                compare(first.fileName, "Mang can ban");
                fuzzyCompare(first.x, 0, 1);
                fuzzyCompare(first.y, 0, 1);
                grid.forceActiveFocus();
                keyClick(Qt.Key_Home);
                keyClick(Qt.Key_Left);
                compare(grid.currentIndex, 0);
                keyClick(Qt.Key_Right);
                compare(grid.currentIndex, 1);
                keyClick(Qt.Key_Home);
                keyClick(Qt.Key_Down);
                compare(grid.currentIndex, Math.min(grid.count - 1, Math.floor(grid.width / grid.cellWidth)));
                keyClick(Qt.Key_Up);
                compare(grid.currentIndex, 0);
                keyClick(Qt.Key_End);
                keyClick(Qt.Key_Right);
                compare(grid.currentIndex, grid.count - 1);
                picker.showHidden = true;
                tryCompare(grid, "count", 5);
                compare(countLabel.text, "5 mục");
                picker.showHidden = false;
                tryCompare(grid, "count", 4);
                fuzzyCompare(grid.itemAtIndex(0).x, 0, 1);
            }
            function test_preview_clears_with_navigation_and_filters() {
                const preview = findChild(window, "filePickerPreview");
                select("mang-co-ban.cyberlab");
                verify(preview.modified !== null);
                picker.filterIndex = 1;
                compare(preview.fileName, "");
                compare(String(preview.fileUrl), "");
                select("mang-co-ban.cyberlab");
                picker.navigate(file("Mang can ban"));
                ready();
                compare(preview.fileName, "");
                compare(preview.fileSize, 0);
                const grid = findChild(window, "filePickerEntries");
                tryCompare(grid, "count", 0);
                waitForRendering(grid);
                picker.selectEntry(file("mang-co-ban.cyberlab"), false, "mang-co-ban.cyberlab");
                compare(preview.fileName, "");
                grid.forceActiveFocus();
                verify(grid.activeFocus);
                compare(picker.selection.length, 0);
                for (const key of [Qt.Key_Left, Qt.Key_Right, Qt.Key_Down, Qt.Key_Up, Qt.Key_Home, Qt.Key_End, Qt.Key_Space, Qt.Key_Return]) {
                    keyClick(key);
                    compare(picker.selection.length, 0, "key=" + key + "; count=" + grid.count + "; model=" + grid.model.items.count + "; selection=" + JSON.stringify(picker.selection));
                }
                compare(grid.currentItem, null);
                compare(picker.selection.length, 0);
                compare(accepted.count, 0);
            }
            function test_card_hover_and_press_are_stable() {
                Studio.Theme.reducedMotion = false;
                const grid = findChild(window, "filePickerEntries");
                tryVerify(() => grid.itemAtIndex(viewIndex("mang-co-ban.cyberlab")) !== null);
                const entry = grid.itemAtIndex(viewIndex("mang-co-ban.cyberlab"));
                const layer = findChild(entry, "filePickerEntryState");
                const original = Qt.rect(entry.x, entry.y, entry.width, entry.height);
                mouseMove(entry);
                tryCompare(layer, "opacity", 0.08);
                mousePress(entry);
                tryCompare(layer, "opacity", 0.12);
                mouseRelease(entry);
                tryCompare(layer, "opacity", 0.08);
                verify(entry.chosen);
                compare(layer.color, Studio.Theme.textOnSurface);
                compare(Qt.rect(entry.x, entry.y, entry.width, entry.height), original);
                mouseMove(findChild(window, "filePickerCancel"));
                tryCompare(layer, "opacity", 0);
            }
            function test_image_preview_data() {
                return [{tag: "dark", width: 1280, theme: "dark"}, {tag: "light", width: 1280, theme: "light"},
                        {tag: "compact", width: 620, theme: "dark"}];
            }
            function test_image_preview(data) {
                window.width = data.width;
                Studio.Theme.themeMode = data.theme;
                picker.filterIndex = 1;
                picker.navigate(file("Pictures"));
                ready();
                const grid = findChild(window, "filePickerEntries");
                tryCompare(grid, "count", 7);
                const imageUrl = Paths.destination(picker.currentFolder, "Landscape 3.svg", "");
                const index = picker.folderModel.indexOf(imageUrl) - picker.dotCount;
                tryVerify(() => grid.itemAtIndex(index) !== null);
                const entry = grid.itemAtIndex(index);
                mouseClick(entry);
                verify(entry.chosen);
                const thumbnail = findChild(entry, "filePickerThumbnail");
                tryCompare(thumbnail, "status", Image.Ready);
                const preview = findChild(window, "filePickerPreview");
                compare(preview.fileName, "Landscape 3.svg");
                compare(Paths.localPath(preview.fileUrl), Paths.localPath(imageUrl));
                compare(preview.imageFile, true);
                verify(preview.fileSize > 0);
                const image = findChild(preview, "filePickerPreviewImage");
                tryCompare(image, "status", Image.Ready);
                compare(preview.visible, picker.width >= 900);
                compare(findChild(window, "filePickerPlaces").visible, picker.width >= 760);
                for (let offset = 0; offset < grid.count; offset++) {
                    const card = grid.itemAtIndex(offset);
                    if (card) verify(card.x >= 0 && card.x + card.width <= grid.width + 1);
                }
                if (checks.screenshotFolder) {
                    let saved = false;
                    picker.contentItem.parent.grabToImage(result => saved = result.saveToFile(checks.screenshotFolder + "/picker-images-" + data.tag + ".png"));
                    tryVerify(() => saved);
                }
            }
            function test_directory_navigation() {
                picker.folderOnly = true;
                const list = findChild(window, "filePickerEntries");
                tryVerify(() => picker.folderModel.indexOf(file("mang-co-ban.cyberlab")) < 0);
                ready();
                tryVerify(() => picker.folderModel.indexOf(file("Mang can ban")) >= 0);
                list.currentIndex = viewIndex("Mang can ban");
                list.forceActiveFocus();
                tryCompare(list, "activeFocus", true);
                keyClick(Qt.Key_Return);
                tryCompare(picker, "currentFolder", Qt.url(file("Mang can ban")));
                ready();
                compare(picker.folderModel.count, picker.dotCount);
                verify(picker.canChoose);
                mouseClick(findChild(window, "filePickerParent"));
                tryCompare(picker, "currentFolder", checks.fixtureFolder);
                ready();
                picker.selectEntry(file("Mang can ban"), true, "Mang can ban");
                picker.choose();
                compare(accepted.count, 1);
                compare(Paths.localPath(picker.selectedFolder), Paths.localPath(file("Mang can ban")));
            }
            function test_navigation_does_not_report_loading_as_error() {
                wait(50);
                errors.clear();
                for (let index = 0; index < 6; index++) {
                    picker.navigate(file("Pictures"));
                    ready();
                    picker.navigate(file("Mang can ban"));
                    ready();
                    picker.navigate(checks.fixtureFolder);
                    ready();
                }
                wait(50);
                compare(errors.count, 0, "Readable folders must not trigger an error popup while loading");
            }
            function test_rapid_navigation_ignores_superseded_folder() {
                wait(50);
                errors.clear();
                for (let index = 0; index < 6; index++) {
                    picker.navigate(file("Pictures"));
                    picker.navigate(file("missing-directory"));
                    picker.navigate(file("Mang can ban"));
                    picker.navigate(checks.fixtureFolder);
                    ready();
                }
                wait(50);
                compare(errors.count, 0);
            }
            function test_reopen_readable_folder_without_error() {
                picker.reject();
                tryCompare(picker, "visible", false);
                wait(50);
                errors.clear();
                picker.open();
                tryCompare(picker, "opened", true);
                ready();
                wait(50);
                compare(errors.count, 0);
            }
            function test_invalid_folder_still_reports_error() {
                wait(50);
                errors.clear();
                picker.navigate(file("missing-directory"));
                tryCompare(picker, "loading", false);
                tryCompare(errors, "count", 1);
                verify(!picker.canChoose);
                verify(findChild(window, "filePickerError").visible);
                picker.navigate(checks.fixtureFolder);
                ready();
                wait(50);
                compare(errors.count, 1);
                verify(!findChild(window, "filePickerError").visible);
            }
            function test_selection_with_spaces_and_url_characters() {
                picker.fileMode = "openMany";
                const grid = findChild(window, "filePickerEntries");
                const index = viewIndex("Mạng #1 % thử.cyberlab");
                tryVerify(() => grid.itemAtIndex(index) !== null);
                const entry = grid.itemAtIndex(index);
                mouseClick(entry);
                verify(entry.chosen);
                compare(picker.selection.length, 1);
                compare(Paths.localPath(picker.selection[0]), Paths.localPath(file("Mạng #1 % thử.cyberlab")));
                mouseClick(entry);
                verify(!entry.chosen);
                compare(picker.selection.length, 0);
                const directory = grid.itemAtIndex(viewIndex("Mang can ban"));
                mouseClick(directory);
                verify(directory.chosen);
                verify(!entry.chosen);
            }
            function test_filters_hidden_and_reset() {
                compare(picker.folderModel.indexOf(file("huong-dan.md")), -1);
                compare(picker.folderModel.indexOf(file(".hidden.cyberlab")), -1);
                select("mang-co-ban.cyberlab");
                picker.filterIndex = 1;
                tryVerify(() => picker.folderModel.indexOf(file("huong-dan.md")) >= 0);
                compare(picker.selection.length, 0);
                mouseClick(findChild(window, "filePickerHidden"));
                tryVerify(() => picker.folderModel.indexOf(file(".hidden.cyberlab")) >= 0);
                mouseClick(findChild(window, "filePickerHidden"));
                tryVerify(() => picker.folderModel.indexOf(file(".hidden.cyberlab")) < 0);
            }
            function test_invalid_and_stale_selection() {
                picker.navigate(file("missing-directory"));
                tryVerify(() => !picker.validFolder);
                tryCompare(picker, "loading", false);
                verify(!picker.canChoose);
                verify(findChild(window, "filePickerError").visible);
                picker.navigate(checks.fixtureFolder);
                ready();
                select("deleted.cyberlab");
                picker.choose();
                compare(accepted.count, 0);
                verify(picker.errorText.length > 0);
                compare(picker.selection.length, 0);
                ignoreWarning(/inotify_add_watch.*Permission denied.*/);
                picker.navigate(file("unreadable"));
                tryVerify(() => !picker.validFolder);
                tryCompare(picker, "loading", false);
                verify(!picker.canChoose);
            }
            function test_invalid_on_open_and_path_entry() {
                picker.reject();
                picker.currentFolder = file("missing-directory");
                picker.open();
                tryCompare(picker, "loading", false);
                verify(!picker.validFolder);
                verify(!picker.canChoose);
                const location = findChild(window, "filePickerPath");
                location.text = Paths.localPath(file("Mang can ban"));
                location.forceActiveFocus();
                keyClick(Qt.Key_Return);
                ready();
                compare(Paths.localPath(picker.currentFolder), Paths.localPath(file("Mang can ban")));
            }
            function test_save_suffix_and_no_overwrite() {
                picker.fileMode = "save";
                picker.defaultSuffix = "cyberlab";
                picker.fileName = "mang-co-ban.cyberlab";
                picker.choose();
                compare(accepted.count, 0);
                verify(picker.errorText.length > 0);
                picker.fileName = "../outside";
                verify(!picker.canChoose);
                picker.fileName = "Bài mới #2 %";
                picker.choose();
                compare(accepted.count, 1);
                compare(Paths.localPath(picker.selectedFile), Paths.localPath(file("Bài mới #2 %.cyberlab")));
            }
            function test_folder_wrapper() {
                picker.reject();
                folderPicker.open();
                tryCompare(folderPicker, "validFolder", true);
                verify(folderPicker.folderOnly);
                folderPicker.choose();
                compare(String(folderPicker.selectedFolder), String(checks.fixtureFolder));
            }
            function test_save_prefill_and_reopen() {
                picker.reject();
                picker.fileMode = "save";
                picker.selectedFile = file("new.cyberlab");
                picker.open();
                ready();
                compare(picker.fileName, "new.cyberlab");
                compare(String(picker.currentFolder), String(checks.fixtureFolder));
                select("mang-co-ban.cyberlab");
                picker.reject();
                picker.open();
                ready();
                compare(picker.selection.length, 0);
            }
            function test_paths() {
                compare(Paths.localPath(file("Mạng #1 % thử.cyberlab")), Paths.localPath(checks.fixtureFolder) + "/Mạng #1 % thử.cyberlab");
                compare(Paths.fromPath("~/child", checks.fixtureFolder), file("child"));
                compare(Paths.fromPath("/tmp/../tmp/a b/#/%"), "file:///tmp/a%20b/%23/%25");
                compare(Paths.localPath("file://remote/tmp/a"), "");
                compare(Paths.localPath("https://example.com/file"), "");
                compare(Paths.localPath("file:///tmp/%00"), "");
                compare(Paths.fromPath("relative"), "");
                compare(Paths.parentFolder("file:///"), "file:///");
                verify(!Paths.validName(".."));
                verify(!Paths.validName("a\nb"));
                compare(Paths.filters("All (*.*)"), ["*"]);
            }
            function test_visual_data() {
                return [{tag: "dark", width: 1000, theme: "dark"}, {tag: "light", width: 1000, theme: "light"}, {tag: "compact", width: 620, theme: "dark"}];
            }
            function test_visual(data) {
                Studio.Theme.themeMode = data.theme;
                window.width = data.width;
                select("mang-co-ban.cyberlab");
                wait(150);
                const list = findChild(window, "filePickerEntries");
                verify(list.width > 200);
                verify(picker.width <= window.width);
                verify(findChild(window, "filePickerAccept").width >= 48);
                if (checks.screenshotFolder) {
                    let saved = false;
                    picker.contentItem.parent.grabToImage(result => saved = result.saveToFile(checks.screenshotFolder + "/picker-" + data.tag + ".png"));
                    tryVerify(() => saved);
                }
            }
        }
    }
}
