// SPDX-License-Identifier: LGPL-2.1-or-later
// Copyright (c) 2025-2026 OficineRobotica
import QtQuick

Rectangle {
    id: sec
    property var th
    property var section
    property bool open: !section.collapsed
    property int shown: {
        var n = 0, h = bridge.hidden
        for (var i = 0; i < section.params.length; ++i)
            if (h.indexOf(section.params[i].name) < 0) n++
        return n
    }
    property string look: th.sectionStyle || "Flat"
    visible: shown > 0
    height: visible ? body.implicitHeight + 18 : 0
    radius: Math.round(6 * th.s)
    // Flat: a plain card; Inset: pressed into the panel; Outset: raised; Outline: a frame around it
    color: look === "Inset" ? th.shade : look === "Outset" ? th.light : look === "Outline" ? "transparent" : th.card
    border.width: look === "Flat" ? 0 : 1
    border.color: look === "Inset" ? Qt.darker(th.shade, 1.12) : look === "Outset" ? th.line : th.line
    clip: true
    onOpenChanged: bridge.setCollapsed(section.title, !open)
    // bevel: a dark line on top for Inset, a dark line at the bottom for Outset
    Rectangle {
        visible: sec.look === "Inset" || sec.look === "Outset"
        x: sec.radius; width: sec.width - 2 * sec.radius; height: 2
        y: sec.look === "Inset" ? 1 : sec.height - 3
        color: Qt.rgba(0, 0, 0, sec.look === "Inset" ? 0.10 : 0.08)
    }

    Column {
        id: body
        x: Math.round(10 * th.s); y: Math.round(8 * th.s)
        width: parent.width - 20
        spacing: 2

        Item {
            width: parent.width
            height: Math.round(24 * th.s)
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: sec.section.title
                color: sec.th.muted
                font.pixelSize: Math.round(12 * th.s); font.family: th.family
                font.bold: true
            }
            Text {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: sec.open ? "−" : "+"
                color: sec.th.muted
                font.pixelSize: Math.round(14 * th.s); font.family: th.family
            }
            MouseArea { anchors.fill: parent; onClicked: sec.open = !sec.open }
        }

        Repeater {
            model: sec.open ? sec.section.params : []
            Loader {
                width: body.width
                property bool hiddenRow: bridge.hidden.indexOf(modelData.name) >= 0
                visible: !hiddenRow
                height: hiddenRow ? 0 : (item ? item.implicitHeight : 0)
                Component.onCompleted: setSource(
                    modelData.kind === "bool" ? "ToggleRow.qml"
                    : modelData.kind === "enum" ? "ChoiceRow.qml"
                    : modelData.kind === "int" ? "StepperRow.qml"
                    : modelData.kind === "color" ? "ColorRow.qml"
                    : modelData.kind === "vector" ? "VectorRow.qml"
                    : modelData.kind === "gallery" ? "GalleryRow.qml"
                    : modelData.kind === "light" ? "LightRow.qml"
                    : modelData.kind === "note" ? "NoteRow.qml"
                    : (modelData.kind === "text" || modelData.kind === "native") ? "TextRow.qml"
                    : modelData.kind === "compass" ? "CompassRow.qml" : "NumberRow.qml",
                    { "p": modelData, "th": sec.th })
            }
        }
    }
}
