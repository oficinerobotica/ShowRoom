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
    visible: shown > 0
    height: visible ? body.implicitHeight + 18 : 0
    radius: Math.round(6 * th.s)
    color: th.card
    clip: true

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
