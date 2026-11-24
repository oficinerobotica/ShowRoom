// SPDX-License-Identifier: LGPL-2.1-or-later
// Copyright (c) 2025-2026 OficineRobotica
// A text property: editable, read-only, or shown with a button that opens
// FreeCAD's own editor (placement, links, expressions...).
import QtQuick

Item {
    id: row
    property var p
    property var th
    property string value: { var v = bridge.values[p.name]; return v === undefined ? "" : String(v) }
    implicitHeight: Math.round(30 * th.s)
    // table rows: an expression shows as a violet pill, read-only text with a lock
    property bool table: bridge.tableRows === true
    property bool expr: table && value.indexOf("= ") === 0
    property bool locked: table && p.readOnly && !p.button.length
    width: parent ? parent.width : 0

    Text {
        id: lab
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: Math.round(parent.width * 0.38)
        text: p.label
        color: th.text
        font.pixelSize: Math.round(12 * th.s); font.family: th.family
        elide: Text.ElideRight
    }
    Rectangle {
        id: field
        anchors.left: lab.right
        anchors.leftMargin: Math.round(8 * th.s)
        anchors.right: btn.visible ? btn.left : parent.right
        anchors.rightMargin: btn.visible ? Math.round(6 * th.s) : row.locked ? Math.round(16 * th.s) : 0
        anchors.verticalCenter: parent.verticalCenter
        height: Math.round(24 * th.s)
        radius: Math.round(4 * th.s)
        color: row.expr ? "#ece6fa" : p.readOnly ? "transparent" : th.field
        border.width: input.activeFocus ? 1 : 0
        border.color: th.accent
        TextInput {
            id: input
            anchors.fill: parent
            anchors.leftMargin: Math.round(6 * th.s); anchors.rightMargin: Math.round(6 * th.s)
            verticalAlignment: TextInput.AlignVCenter
            readOnly: p.readOnly
            color: row.expr ? "#5b3fb0" : p.readOnly ? th.muted : th.text
            font.family: row.expr ? "monospace" : th.family
            selectionColor: th.accent
            font.pixelSize: Math.round(12 * th.s)
            selectByMouse: true
            clip: true
            text: row.value
            onEditingFinished: { if (!p.readOnly && text !== row.value) bridge.setValue(p.name, text); text = Qt.binding(function() { return row.value }) }
        }
    }
    Rectangle {
        id: btn
        visible: p.button.length > 0
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: bt.implicitWidth + Math.round(16 * th.s); height: Math.round(24 * th.s)
        radius: Math.round(6 * th.s)
        color: ma.containsMouse ? th.accent : th.field
        Text { id: bt; anchors.centerIn: parent; text: p.button; font.italic: p.button === "fx"; font.bold: p.button === "fx"; color: ma.containsMouse ? th.accentText : th.text; font.pixelSize: Math.round(11 * th.s); font.family: th.family }
        MouseArea { id: ma; cursorShape: Qt.PointingHandCursor; anchors.fill: parent; hoverEnabled: true; onClicked: bridge.trigger(p.action) }
    }
    Canvas {        // lock (table rows, read only)
        visible: row.locked
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        width: Math.round(11 * th.s); height: Math.round(12 * th.s)
        property color c: th.muted
        onPaint: {
            var g = getContext("2d"), w = width, h = height
            g.reset(); g.strokeStyle = c; g.lineWidth = 1.4
            g.strokeRect(1, h * 0.45, w - 2, h * 0.5)
            g.beginPath(); g.arc(w / 2, h * 0.45, w * 0.3, Math.PI, 0); g.stroke()
        }
    }
}
