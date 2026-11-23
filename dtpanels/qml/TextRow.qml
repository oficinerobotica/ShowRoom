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
        anchors.rightMargin: btn.visible ? Math.round(6 * th.s) : 0
        anchors.verticalCenter: parent.verticalCenter
        height: Math.round(24 * th.s)
        radius: Math.round(4 * th.s)
        color: p.readOnly ? "transparent" : th.field
        border.width: input.activeFocus ? 1 : 0
        border.color: th.accent
        TextInput {
            id: input
            anchors.fill: parent
            anchors.leftMargin: Math.round(6 * th.s); anchors.rightMargin: Math.round(6 * th.s)
            verticalAlignment: TextInput.AlignVCenter
            readOnly: p.readOnly
            color: p.readOnly ? th.muted : th.text
            selectionColor: th.accent
            font.pixelSize: Math.round(12 * th.s); font.family: th.family
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
        Text { id: bt; anchors.centerIn: parent; text: p.button; color: ma.containsMouse ? th.accentText : th.text; font.pixelSize: Math.round(11 * th.s); font.family: th.family }
        MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; onClicked: bridge.trigger(p.action) }
    }
}
