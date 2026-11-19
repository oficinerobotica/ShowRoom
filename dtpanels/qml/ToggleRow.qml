// SPDX-License-Identifier: LGPL-2.1-or-later
// Copyright (c) 2025-2026 OficineRobotica
import QtQuick

Item {
    id: row
    property var p
    property var th
    property bool value: bridge.values[p.name] === true
    // greyed out: an option this system cannot run
    readonly property bool disabled: p.disabled === true
    readonly property real disabledOpacity: 0.4
    opacity: disabled ? disabledOpacity : 1.0
    implicitHeight: Math.round(34 * th.s)
    width: parent ? parent.width : 0

    Text {
        anchors.left: parent.left
        anchors.right: sw.left
        anchors.verticalCenter: parent.verticalCenter
        text: p.label
        color: th.text
        font.pixelSize: Math.round(12 * th.s); font.family: th.family
        elide: Text.ElideRight
    }
    Rectangle {
        id: sw
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: Math.round(38 * th.s); height: Math.round(20 * th.s); radius: Math.round(6 * th.s)
        color: row.value ? th.accent : th.line
        Behavior on color { ColorAnimation { duration: 120 } }
        Rectangle {
            x: row.value ? parent.width - width - 2 : 2
            anchors.verticalCenter: parent.verticalCenter
            width: Math.round(16 * th.s); height: Math.round(16 * th.s); radius: Math.round(8 * th.s)
            color: "white"
            Behavior on x { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        }
        MouseArea {
            anchors.fill: parent; anchors.margins: -4
            enabled: !row.disabled
            onClicked: bridge.setValue(p.name, !row.value)
        }
    }
}
