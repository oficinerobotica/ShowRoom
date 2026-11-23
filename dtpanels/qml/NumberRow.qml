// SPDX-License-Identifier: LGPL-2.1-or-later
// Copyright (c) 2025-2026 OficineRobotica
import QtQuick

Item {
    id: row
    property var p
    property var th
    property real value: { var v = bridge.values[p.name]; return v === undefined ? 0 : v }
    implicitHeight: Math.round((p.slider ? 48 : 30) * th.s)
    width: parent ? parent.width : 0

    function commit(v) {
        if (isNaN(v)) return
        bridge.setValue(p.name, Math.round(v * 1000) / 1000)
    }
    function fmt(v) { return (p.special && Number(v) === 0) ? p.special : Number(v).toFixed(p.decimals) }

    Text {
        anchors.left: parent.left
        anchors.right: field.left
        anchors.rightMargin: Math.round(8 * th.s)
        y: Math.round(8 * th.s)
        text: p.label
        color: th.text
        font.pixelSize: Math.round(12 * th.s); font.family: th.family
        elide: Text.ElideRight
    }
    Rectangle {
        id: field
        anchors.right: parent.right
        y: 3
        width: Math.round(92 * th.s); height: Math.round(24 * th.s)
        radius: Math.round(4 * th.s)
        color: th.field
        border.width: input.activeFocus ? 1 : 0
        border.color: th.accent
        TextInput {
            id: input
            anchors.left: parent.left
            anchors.right: unit.left
            anchors.margins: Math.round(6 * th.s)
            anchors.verticalCenter: parent.verticalCenter
            horizontalAlignment: TextInput.AlignRight
            color: th.text
            selectionColor: th.accent
            font.pixelSize: Math.round(12 * th.s); font.family: th.family
            selectByMouse: true
            clip: true
            text: row.fmt(row.value)
            onEditingFinished: { var t = text.replace(",", "."); row.commit(p.special && t === p.special ? 0 : parseFloat(t)); text = Qt.binding(function() { return row.fmt(row.value) }) }
            Keys.onUpPressed: row.commit(row.value + p.step)
            Keys.onDownPressed: row.commit(row.value - p.step)
        }
        Text {
            id: unit
            anchors.right: parent.right
            anchors.rightMargin: Math.round(6 * th.s)
            anchors.verticalCenter: parent.verticalCenter
            text: p.unit
            color: th.muted
            font.pixelSize: Math.round(11 * th.s); font.family: th.family
        }
    }
    // slider
    Item {
        id: track
        visible: p.slider
        anchors.left: parent.left
        anchors.right: parent.right
        y: Math.round(30 * th.s)
        height: Math.round(16 * th.s)
        property real ratio: Math.max(0, Math.min(1, (row.value - p.min) / (p.max - p.min)))
        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 3; radius: 2; color: th.line }
        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width * track.ratio; height: 3; radius: 2; color: th.accent }
        Rectangle {
            x: (parent.width - width) * track.ratio
            anchors.verticalCenter: parent.verticalCenter
            width: Math.round(12 * th.s); height: Math.round(12 * th.s); radius: Math.round(6 * th.s)
            color: ma.pressed ? th.accent : th.text
            border.width: 2
            border.color: th.accent
        }
        MouseArea {
            id: ma
            anchors.fill: parent
            anchors.margins: -3
            preventStealing: true
            function pick(mx) {
                var r = Math.max(0, Math.min(1, (mx - 6) / (width - 12)))
                var v = p.min + r * (p.max - p.min)
                row.commit(Math.round(v / p.step) * p.step)
            }
            onPressed: function(mouse) { input.focus = false; pick(mouse.x) }
            onPositionChanged: function(mouse) { if (pressed) pick(mouse.x) }
        }
    }
}
