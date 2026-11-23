// SPDX-License-Identifier: LGPL-2.1-or-later
// Copyright (c) 2025-2026 OficineRobotica
// Three numbers (x, y, z) on one line.
import QtQuick

Item {
    id: row
    property var p
    property var th
    property var value: { var v = bridge.values[p.name]; return v === undefined ? [0, 0, 0] : v }
    implicitHeight: Math.round(54 * th.s)
    width: parent ? parent.width : 0

    Text {
        x: 0; y: Math.round(4 * th.s)
        text: p.label
        color: th.text
        font.pixelSize: Math.round(12 * th.s); font.family: th.family
    }
    Row {
        anchors.left: parent.left
        anchors.right: parent.right
        y: Math.round(24 * th.s)
        spacing: Math.round(6 * th.s)
        Repeater {
            model: p.components && p.components.length === 3 ? p.components : ["X", "Y", "Z"]
            Rectangle {
                width: Math.floor((row.width - 2 * Math.round(6 * th.s)) / 3)
                height: Math.round(24 * th.s)
                radius: Math.round(4 * th.s)
                color: th.field
                border.width: input.activeFocus ? 1 : 0
                border.color: th.accent
                Text {
                    id: axis
                    x: Math.round(6 * th.s)
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData
                    color: index === 0 ? "#d6453d" : index === 1 ? "#2e9e6b" : "#3d7bd6"
                    font.pixelSize: Math.round(11 * th.s); font.family: th.family; font.bold: true
                }
                TextInput {
                    id: input
                    anchors.left: axis.right
                    anchors.right: parent.right
                    anchors.margins: Math.round(6 * th.s)
                    anchors.verticalCenter: parent.verticalCenter
                    horizontalAlignment: TextInput.AlignRight
                    color: th.text
                    selectionColor: th.accent
                    font.pixelSize: Math.round(12 * th.s); font.family: th.family
                    selectByMouse: true
                    clip: true
                    text: Number(row.value[index]).toFixed(p.decimals)
                    onEditingFinished: {
                        var v = parseFloat(text.replace(",", "."))
                        if (!isNaN(v)) {
                            var out = [row.value[0], row.value[1], row.value[2]]
                            out[index] = v
                            bridge.setValue(p.name, out)
                        }
                        text = Qt.binding(function() { return Number(row.value[index]).toFixed(p.decimals) })
                    }
                }
            }
        }
    }
}
