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
    property bool bevel: look === "Inset" || look === "Outset"
    property int bw: Math.max(2, Math.round(2 * th.s))
    radius: Math.round(6 * th.s)
    // Flat: a plain card; Inset: pressed into the panel; Outset: raised; Outline: a frame around it
    color: look === "Outline" ? "transparent" : th.card
    border.width: look === "Outline" ? 1 : 0
    border.color: th.line
    clip: true
    onOpenChanged: bridge.setCollapsed(section.title, !open)
    // bevel: Inset is dark on top and left, light on bottom and right; Outset the opposite
    property color tl: look === "Inset" ? th.bevelDark : th.bevelLight
    property color br: look === "Inset" ? th.bevelLight : th.bevelDark
    // a rounded frame: the top-left half in one colour, the bottom-right half in the other
    Canvas {
        visible: sec.bevel
        anchors.fill: parent
        property color c1: sec.tl
        property color c2: sec.br
        onC1Changed: requestPaint()
        onC2Changed: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var g = getContext("2d"), b = sec.bw, w = width, h = height, r = sec.radius
            g.reset()
            if (w <= 0 || h <= 0) return
            function frame(color) {
                var i = b / 2, rr = Math.max(0, r - i)
                g.strokeStyle = color
                g.lineWidth = b
                g.beginPath()
                g.moveTo(i + rr, i)
                g.lineTo(w - i - rr, i); g.arcTo(w - i, i, w - i, i + rr, rr)
                g.lineTo(w - i, h - i - rr); g.arcTo(w - i, h - i, w - i - rr, h - i, rr)
                g.lineTo(i + rr, h - i); g.arcTo(i, h - i, i, h - i - rr, rr)
                g.lineTo(i, i + rr); g.arcTo(i, i, i + rr, i, rr)
                g.closePath()
                g.stroke()
            }
            // split along the diagonal through the top-right and bottom-left corners
            g.save()
            g.beginPath(); g.moveTo(0, 0); g.lineTo(w, 0); g.lineTo(w - r, r); g.lineTo(r, h - r); g.lineTo(0, h); g.closePath()
            g.clip(); frame(sec.tl); g.restore()
            g.save()
            g.beginPath(); g.moveTo(w, 0); g.lineTo(w, h); g.lineTo(0, h); g.lineTo(r, h - r); g.lineTo(w - r, r); g.closePath()
            g.clip(); frame(sec.br); g.restore()
        }
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
