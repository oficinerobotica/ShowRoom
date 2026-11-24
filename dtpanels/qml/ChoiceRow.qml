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
    // table rows: a short choice sits as a small segmented control on the label's line
    property bool side: bridge.tableRows === true && compact
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
            Rectangle {     // segmented control (table rows)
                visible: row.side
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                width: seg.implicitWidth + 4; height: Math.round(24 * th.s); radius: Math.round(7 * th.s)
                color: th.field
                Row {
                    id: seg
                    x: 2; anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    Repeater {
                        model: row.side ? p.options : []
                        Rectangle {
                            property bool sel: modelData === row.value
                            width: sl.implicitWidth + Math.round(14 * th.s); height: Math.round(20 * th.s); radius: Math.round(5 * th.s)
                            color: sel ? th.card : "transparent"
                            border.width: sel ? 1 : 0; border.color: th.line
                            Text { id: sl; anchors.centerIn: parent; text: (p.optionLabels && p.optionLabels[index] !== undefined) ? p.optionLabels[index] : String(modelData); color: parent.sel ? th.accent : th.text; font.pixelSize: Math.round(11 * th.s); font.family: th.family; font.bold: parent.sel }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.setValue(p.name, modelData) }
                        }
                    }
                }
            }
            Rectangle {
                visible: !row.inline
                anchors.right: parent.right
                width: cur.implicitWidth + Math.round(30 * th.s) + (p.isLink ? Math.round(14 * th.s) : 0)
                height: Math.round(24 * th.s); radius: p.isLink ? height / 2 : Math.round(6 * th.s)
                // a link is a chip: it names another object
                color: p.isLink ? Qt.rgba(Qt.color(th.accent).r, Qt.color(th.accent).g, Qt.color(th.accent).b, 0.13) : th.field
                Image { visible: p.isLink && p.icon !== ""; source: p.isLink ? p.icon : ""; x: Math.round(8 * th.s); anchors.verticalCenter: parent.verticalCenter; width: Math.round(11 * th.s); height: width; sourceSize.width: 48; sourceSize.height: 48 }
                Text { id: cur; x: Math.round(8 * th.s) + (p.isLink ? Math.round(14 * th.s) : 0); color: p.isLink ? th.accent : th.text; anchors.verticalCenter: parent.verticalCenter; text: row.labelOf(row.value); font.pixelSize: Math.round(12 * th.s); font.family: th.family; font.bold: true }
                Text { anchors.right: parent.right; anchors.rightMargin: Math.round(8 * th.s); anchors.verticalCenter: parent.verticalCenter; text: row.open ? "▴" : "▾"; color: th.muted; font.pixelSize: Math.round(10 * th.s) ; font.family: th.family}
                MouseArea { anchors.fill: parent; onClicked: row.open = !row.open }
            }
        }
        Flow {
            width: parent.width
            spacing: Math.round(4 * th.s)
            visible: (row.inline && !row.side) || row.open
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
