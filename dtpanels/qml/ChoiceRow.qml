// SPDX-License-Identifier: LGPL-2.1-or-later
// Copyright (c) 2025-2026 OficineRobotica
import QtQuick

Item {
    id: row
    property var p
    property var th
    property string value: { var v = bridge.values[p.name]; return v === undefined ? "" : v }
    property bool compact: p.options.length <= 3 && p.optionLabels.join("").length <= 24
    property bool inline: compact || p.options.length <= 4
    property bool open: false
    implicitHeight: col.implicitHeight + 8
    width: parent ? parent.width : 0

    function labelOf(v) { var i = p.options.indexOf(v); return i < 0 ? v : p.optionLabels[i] }

    Column {
        id: col
        y: Math.round(4 * th.s)
        width: parent.width
        spacing: Math.round(6 * th.s)
        Item {
            width: parent.width
            height: Math.round(24 * th.s)
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: p.label
                color: th.text
                font.pixelSize: Math.round(12 * th.s); font.family: th.family
            }
            Rectangle {
                visible: !row.inline
                anchors.right: parent.right
                width: cur.implicitWidth + Math.round(30 * th.s); height: Math.round(24 * th.s); radius: Math.round(6 * th.s)
                color: th.field
                Text { id: cur; x: Math.round(8 * th.s); anchors.verticalCenter: parent.verticalCenter; text: row.labelOf(row.value); color: th.text; font.pixelSize: Math.round(12 * th.s); font.family: th.family; font.bold: true }
                Text { anchors.right: parent.right; anchors.rightMargin: Math.round(8 * th.s); anchors.verticalCenter: parent.verticalCenter; text: row.open ? "▴" : "▾"; color: th.muted; font.pixelSize: Math.round(10 * th.s) ; font.family: th.family}
                MouseArea { anchors.fill: parent; onClicked: row.open = !row.open }
            }
        }
        Flow {
            width: parent.width
            spacing: Math.round(4 * th.s)
            visible: row.inline || row.open
            Repeater {
                model: p.options
                Rectangle {
                    property bool sel: modelData === row.value
                    width: row.compact ? Math.floor((col.width - Math.round(4 * th.s) * (p.options.length - 1)) / p.options.length) - 1 : lab.implicitWidth + Math.round(16 * th.s)
                    height: Math.round(24 * th.s); radius: Math.round(6 * th.s)
                    color: sel ? th.accent : th.field
                    Text { id: lab; anchors.centerIn: parent; text: (p.optionLabels && p.optionLabels[index] !== undefined) ? p.optionLabels[index] : String(modelData); color: parent.sel ? th.accentText : th.text; font.pixelSize: Math.round(11 * th.s); font.family: th.family; font.bold: parent.sel }
                    MouseArea { anchors.fill: parent; onClicked: { bridge.setValue(p.name, modelData); row.open = false } }
                }
            }
        }
    }
}
