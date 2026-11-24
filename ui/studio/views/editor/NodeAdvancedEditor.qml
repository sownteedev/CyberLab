import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: panel
    required property var editor
    readonly property var node: editor.document && editor.document.nodes[nodeIndex] ? editor.document.nodes[nodeIndex] : null
    required property int nodeIndex
    enabled: !editor.backend.busy
    spacing: Studio.Theme.space8

    EditorDisclosure {
        objectName: "nodeResourcesAdvanced"
        title: qsTr("Tài nguyên")
        expanded: true
        GridLayout {
            Layout.fillWidth: true
            columns: width >= 620 ? 3 : width >= 400 ? 2 : 1
            columnSpacing: Studio.Theme.space16
            rowSpacing: Studio.Theme.space12
            EditorField {
                label: qsTr("RAM (MiB)")
                EditorNumberField {
                    objectName: "nodeResourceMemory"
                    Accessible.name: qsTr("RAM (MiB)")
                    from: panel.node && panel.node.software && panel.node.software.gui ? 1024 : 64
                    implicitHeight: Studio.Theme.controlHeight
                    stepSize: 16
                    to: panel.node && panel.node.image === "cyberlab/ubuntu:24.04-1" ? 2048 : 512
                    value: panel.node && panel.node.resources ? panel.node.resources.memory_mb || 128 : 128
                    onValueModified: panel.editor.change("nodes", panel.nodeIndex, "resources", Object.assign({}, panel.node.resources || {}, {memory_mb: value}))
                }
            }
            EditorField {
                label: qsTr("CPU (mCPU)")
                EditorNumberField {
                    objectName: "nodeResourceCpu"
                    Accessible.name: qsTr("CPU, 1000 mCPU bằng một nhân")
                    from: 100
                    implicitHeight: Studio.Theme.controlHeight
                    stepSize: 100
                    to: panel.node && panel.node.image === "cyberlab/ubuntu:24.04-1" ? 2000 : 1000
                    value: panel.node && panel.node.resources ? panel.node.resources.cpu_millicores || 500 : 500
                    onValueModified: panel.editor.change("nodes", panel.nodeIndex, "resources", Object.assign({}, panel.node.resources || {}, {cpu_millicores: value}))
                }
            }
            EditorField {
                label: qsTr("Số bản máy")
                EditorNumberField {
                    Accessible.name: qsTr("Số bản máy")
                    from: 1
                    implicitHeight: Studio.Theme.controlHeight
                    to: 4
                    value: panel.node ? panel.node.clone || 1 : 1
                    onValueModified: panel.editor.change("nodes", panel.nodeIndex, "clone", value)
                }
            }
        }
    }
    EditorDisclosure {
        objectName: "nodeTerminalAdvanced"
        title: qsTr("Terminal")
        iconName: "terminal"
        GridLayout {
            Layout.fillWidth: true
            columns: width >= 620 ? 2 : 1
            columnSpacing: Studio.Theme.space16
            rowSpacing: Studio.Theme.space12
            EditorField {
                label: qsTr("Nhóm")
                StudioTextField {
                    Layout.fillWidth: true
                    Accessible.name: qsTr("Nhóm terminal")
                    placeholderText: "client"
                    text: panel.node ? panel.node.terminal_group || "" : ""
                    onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "terminal_group", text.trim())
                }
            }
            EditorField {
                label: qsTr("Tiêu đề")
                StudioTextField {
                    Layout.fillWidth: true
                    Accessible.name: qsTr("Tiêu đề terminal")
                    placeholderText: "client@lab"
                    text: panel.node ? panel.node.terminal_title || "" : ""
                    onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "terminal_title", text.trim())
                }
            }
        }
    }
    EditorDisclosure {
        objectName: "nodeNetworkAdvanced"
        title: qsTr("Tên máy và phân giải mạng")
        iconName: "lan"
        GridLayout {
            Layout.fillWidth: true
            columns: width >= 620 ? 2 : 1
            columnSpacing: Studio.Theme.space16
            rowSpacing: Studio.Theme.space12
            EditorField {
                label: qsTr("Tên máy trong hệ thống")
                StudioTextField {
                    Layout.fillWidth: true
                    Accessible.name: "Hostname"
                    placeholderText: panel.node ? panel.node.id : ""
                    text: panel.node ? panel.node.hostname || "" : ""
                    onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "hostname", text)
                }
            }
            EditorField {
                label: qsTr("Tên thay thế")
                StudioTextField {
                    Layout.fillWidth: true
                    Accessible.name: qsTr("Alias, cách nhau bằng dấu phẩy")
                    placeholderText: "client-box, workstation"
                    text: panel.node ? (panel.node.aliases || []).join(", ") : ""
                    onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "aliases", text.split(",").map(value => value.trim()).filter(Boolean))
                }
            }
            EditorField {
                label: qsTr("Tên máy và IP bổ sung")
                StudioTextField {
                    Layout.fillWidth: true
                    objectName: "nodeExtraHosts"
                    Accessible.name: qsTr("Hosts bổ sung, host=IP, cách nhau bằng dấu phẩy")
                    placeholderText: "server=10.0.0.2"
                    text: panel.node ? Object.keys(panel.node.extra_hosts || {}).map(host => host + "=" + panel.node.extra_hosts[host]).join(", ") : ""
                    onEditingFinished: {
                        const hosts = {};
                        text.split(",").map(value => value.trim()).filter(Boolean).forEach(item => {
                            const parts = item.split("=");
                            if (parts.length === 2) hosts[parts[0].trim()] = parts[1].trim();
                        });
                        panel.editor.change("nodes", panel.nodeIndex, "extra_hosts", hosts);
                    }
                }
            }
            EditorField {
                label: "DNS"
                StudioTextField {
                    Layout.fillWidth: true
                    Accessible.name: qsTr("DNS, IP cách nhau bằng dấu phẩy")
                    placeholderText: "10.0.0.2, 10.0.0.3"
                    text: panel.node ? (panel.node.dns || []).join(", ") : ""
                    onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "dns", text.split(",").map(value => value.trim()).filter(Boolean))
                }
            }
            EditorField {
                label: qsTr("Chờ máy khởi động")
                StudioTextField {
                    Layout.fillWidth: true
                    Accessible.name: qsTr("Máy cần chờ, cách nhau bằng dấu phẩy")
                    placeholderText: "server, db"
                    text: panel.node ? (panel.node.wait_for || []).join(", ") : ""
                    onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "wait_for", text.split(",").map(value => value.trim()).filter(Boolean))
                }
            }
        }
    }
    EditorDisclosure {
        objectName: "nodeAccountAdvanced"
        title: qsTr("Tài khoản nâng cao")
        StudioToggle {
            Layout.fillWidth: true
            text: qsTr("Tài khoản tùy chỉnh")
            checked: !!panel.node && !!panel.node.user
            onToggled: panel.editor.change("nodes", panel.nodeIndex, "user", checked ? {name: "", uid: 1000, gid: 1000, home: "/home/", shell: "/bin/sh"} : null)
        }
        Label {
            Layout.fillWidth: true
            text: qsTr("Tài khoản phải được môi trường hỗ trợ.")
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            wrapMode: Text.WordWrap
        }
        GridLayout {
            Layout.fillWidth: true
            visible: !!panel.node && !!panel.node.user
            columns: width >= 620 ? 2 : 1
            columnSpacing: Studio.Theme.space16
            rowSpacing: Studio.Theme.space12
            EditorField {
                label: qsTr("Tên đăng nhập")
                StudioTextField {
                    Layout.fillWidth: true
                    Accessible.name: qsTr("Tên tài khoản tùy chỉnh")
                    text: panel.node && panel.node.user ? panel.node.user.name : ""
                    onEditingFinished: panel.editor.userField(panel.nodeIndex, "name", text)
                }
            }
            EditorField {
                label: qsTr("Trình dòng lệnh")
                StudioComboBox {
                    Layout.fillWidth: true
                    Accessible.name: "Shell"
                    currentIndex: panel.node && panel.node.user ? model.indexOf(panel.node.user.shell) : 0
                    model: ["/bin/sh", "/bin/bash"]
                    onActivated: panel.editor.userField(panel.nodeIndex, "shell", currentText)
                }
            }
            EditorField {
                label: "UID"
                EditorNumberField {
                    Accessible.name: "UID"
                    editable: true
                    from: 1000
                    implicitHeight: Studio.Theme.controlHeight
                    to: 60000
                    value: panel.node && panel.node.user ? panel.node.user.uid : 2000
                    onValueModified: panel.editor.userField(panel.nodeIndex, "uid", value)
                }
            }
            EditorField {
                label: "GID"
                EditorNumberField {
                    Accessible.name: "GID"
                    editable: true
                    from: 1000
                    implicitHeight: Studio.Theme.controlHeight
                    to: 60000
                    value: panel.node && panel.node.user ? panel.node.user.gid : 2000
                    onValueModified: panel.editor.userField(panel.nodeIndex, "gid", value)
                }
            }
        }
        Label {
            Layout.fillWidth: true
            text: panel.node && panel.node.user ? panel.node.user.home : ""
            textFormat: Text.PlainText
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            wrapMode: Text.WrapAnywhere
        }
    }
}
