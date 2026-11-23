// SPDX-License-Identifier: LGPL-2.1-or-later
// Copyright (c) 2025-2026 OficineRobotica
// One light of the document: on/off, intensity, shadows, and a button to edit it.
import QtQuick

Item {
    id: row
    property var p
    property var th
    property var value: { var v = bridge.values[p.name]; return v === undefined ? {} : v }
    implicitHeight: Math.round(52 * th.s)
    width: parent ? parent.width : 0

    // on / off
    Rectangle {
        id: dot
        x: 0; y: Math.round(4 * th.s)
        width: Math.round(18 * th.s); height: Math.round(18 * th.s); radius: Math.round(9 * th.s)
        color: row.value.on ? th.accent : "transparent"
        border.width: 2
        border.color: row.value.on ? th.accent : th.line
        // the light's own colour in the middle
        Rectangle {
            anchors.centerIn: parent
            visible: row.value.on === true
            width: parent.width * 0.45; height: width; radius: width / 2
            color: row.value.color || "#ffffff"
        }
        MouseArea { anchors.fill: parent; anchors.margins: -4; onClicked: bridge.setValue(p.name + "/on", !row.value.on) }
    }
    Text {
        anchors.left: dot.right; anchors.leftMargin: Math.round(8 * th.s)
        anchors.right: buttons.left; anchors.rightMargin: Math.round(6 * th.s)
        y: Math.round(4 * th.s)
        text: p.label
        color: row.value.on ? th.text : th.muted
        font.pixelSize: Math.round(12 * th.s); font.family: th.family
        elide: Text.ElideRight
    }
    Row {
        id: buttons
        anchors.right: parent.right
        y: Math.round(2 * th.s)
        spacing: Math.round(4 * th.s)
        Rectangle {
            visible: row.value.canCast === true
            width: sh.implicitWidth + Math.round(12 * th.s); height: Math.round(20 * th.s); radius: Math.round(4 * th.s)
            color: row.value.cast ? th.accent : th.field
            Text { id: sh; anchors.centerIn: parent; text: p.shadowLabel; color: row.value.cast ? th.accentText : th.muted; font.pixelSize: Math.round(10 * th.s); font.family: th.family }
            MouseArea { anchors.fill: parent; onClicked: bridge.setValue(p.name + "/cast", !row.value.cast) }
        }
        Rectangle {
            width: ed.implicitWidth + Math.round(12 * th.s); height: Math.round(20 * th.s); radius: Math.round(4 * th.s)
            color: th.field
            border.width: 1; border.color: th.line
            Text { id: ed; anchors.centerIn: parent; text: "…"; color: th.text; font.pixelSize: Math.round(11 * th.s); font.family: th.family; font.bold: true }
            MouseArea { anchors.fill: parent; onClicked: bridge.trigger("edit:" + p.name) }
        }
    }
    // intensity
    Item {
        id: track
        anchors.left: parent.left; anchors.leftMargin: Math.round(26 * th.s)
        anchors.right: parent.right
        y: Math.round(28 * th.s)
        height: Math.round(16 * th.s)
        opacity: row.value.on ? 1.0 : 0.45
        property real ratio: Math.max(0, Math.min(1, row.value.intensity || 0))
        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: Math.max(6, Math.round(6 * th.s)); radius: height / 2; color: th.line }
        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width * track.ratio; height: Math.max(6, Math.round(6 * th.s)); radius: height / 2; color: th.accent }
        Rectangle {
            x: (parent.width - width) * track.ratio
            anchors.verticalCenter: parent.verticalCenter
            width: Math.round(18 * th.s); height: width; radius: width / 2
            color: th.accent
            border.width: Math.max(2, Math.round(3 * th.s)); border.color: "white"
            scale: ma.pressed ? 1.15 : 1.0
            Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutBack } }
            Rectangle { z: -1; anchors.centerIn: parent; anchors.verticalCenterOffset: 1; width: parent.width + 2; height: width; radius: width / 2; color: Qt.rgba(0, 0, 0, 0.18) }
        }
        MouseArea {
            id: ma
            anchors.fill: parent; anchors.margins: -3
            preventStealing: true
            function pick(mx) { bridge.setValue(p.name + "/intensity", Math.round(Math.max(0, Math.min(1, (mx - 6) / (width - 12))) * 100) / 100) }
            onPressed: function(mouse) { pick(mouse.x) }
            onPositionChanged: function(mouse) { if (pressed) pick(mouse.x) }
        }
    }
}
