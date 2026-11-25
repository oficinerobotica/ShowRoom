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
    // table rows (property editor): a column of type icons, lines between rows
    property bool table: bridge.tableRows === true
    property int iconCol: table ? Math.round(24 * th.s) : 0
    property int edited: {
        var n = 0, v = bridge.values
        for (var i = 0; i < section.params.length; ++i) {
            var q = section.params[i]
            if (q.hasDefault && String(v[q.name]) !== String(q["default"])) n++
        }
        return n
    }
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
            visible: sec.section.title !== ""
            height: visible ? Math.round(24 * th.s) : 0
            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: Math.round(6 * th.s)
                Text {
                    text: sec.table ? sec.section.title.toUpperCase() : sec.section.title
                    color: sec.th.muted
                    font.pixelSize: Math.round((sec.table ? 11 : 12) * th.s); font.family: th.family
                    font.bold: true
                    font.letterSpacing: sec.table ? 0.8 : 0
                }
                Text {      // table rows: how many properties
                    visible: sec.table
                    text: sec.shown
                    color: sec.th.muted; opacity: 0.8
                    font.pixelSize: Math.round(11 * th.s); font.family: th.family
                }
            }
            Text {          // table rows: how many differ from the default
                visible: sec.table && sec.edited > 0
                anchors.right: tri.left; anchors.rightMargin: Math.round(8 * th.s)
                anchors.verticalCenter: parent.verticalCenter
                text: "Edited " + sec.edited
                color: sec.th.accent
                font.pixelSize: Math.round(11 * th.s); font.family: th.family
            }
            // collapse triangle, drawn so that it sits on the title's centre line
            Canvas {
                id: tri
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: Math.round(12 * th.s); height: Math.round(12 * th.s)
                rotation: sec.open ? 0 : -90
                Behavior on rotation { NumberAnimation { duration: 120 } }
                property color c: sec.th.muted
                onCChanged: requestPaint()
                onPaint: {
                    var g = getContext("2d"), w = width, h = height
                    g.reset(); g.fillStyle = c
                    g.beginPath(); g.moveTo(w * 0.1, h * 0.25); g.lineTo(w * 0.9, h * 0.25); g.lineTo(w * 0.5, h * 0.8); g.closePath(); g.fill()
                }
            }
            MouseArea { anchors.fill: parent; onClicked: sec.open = !sec.open }
        }

        Repeater {
            model: sec.open ? sec.section.params : []
            Loader {
                x: sec.iconCol
                width: body.width - sec.iconCol
                property bool hiddenRow: bridge.hidden.indexOf(modelData.name) >= 0
                visible: !hiddenRow
                height: hiddenRow ? 0 : (item ? item.implicitHeight + (sec.table ? Math.round(6 * sec.th.s) : 0) : 0)
                // table rows: the row lights up under the mouse, a hairline below it, its type icon
                Rectangle {
                    visible: sec.table && hover.containsMouse
                    z: -1
                    x: -sec.iconCol - Math.round(4 * sec.th.s); y: -Math.round(1 * sec.th.s)
                    width: parent.width + sec.iconCol + Math.round(8 * sec.th.s); height: parent.height
                    radius: Math.round(6 * sec.th.s)
                    color: Qt.rgba(Qt.color(sec.th.accent).r, Qt.color(sec.th.accent).g, Qt.color(sec.th.accent).b, 0.07)
                }
                MouseArea { id: hover; anchors.fill: parent; anchors.leftMargin: -sec.iconCol; hoverEnabled: sec.table; acceptedButtons: Qt.NoButton }
                Image {
                    visible: sec.table && modelData.icon !== ""
                    source: sec.table ? modelData.icon : ""
                    x: -sec.iconCol; y: Math.round(7 * sec.th.s)
                    width: Math.round(14 * sec.th.s); height: width
                    sourceSize.width: 48; sourceSize.height: 48
                }
                Rectangle {
                    visible: sec.table
                    x: -sec.iconCol; y: parent.height - 1
                    width: parent.width + sec.iconCol; height: 1
                    color: sec.th.line; opacity: 0.55
                }
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
                // right click: FreeCAD's own menu for the property (left clicks go through)
                MouseArea {
                    anchors.fill: parent
                    anchors.leftMargin: -sec.iconCol      // the type icon too
                    z: 10
                    acceptedButtons: Qt.RightButton
                    onClicked: bridge.contextMenu(modelData.name)
                }
                // changed from the default: a dot in the margin; clicking it puts the default back
                property bool changed: modelData.hasDefault && !hiddenRow
                    && String(bridge.values[modelData.name]) !== String(modelData["default"])
                Rectangle {
                    visible: parent.changed
                    x: -sec.iconCol - Math.round(8 * sec.th.s); y: Math.round(12 * sec.th.s)
                    width: Math.round(6 * sec.th.s); height: width; radius: width / 2
                    color: sec.th.accent
                    SequentialAnimation on opacity {
                        running: parent.visible; loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.35; duration: 900; easing.type: Easing.InOutSine }
                        NumberAnimation { from: 0.35; to: 1.0; duration: 900; easing.type: Easing.InOutSine }
                    }
                    MouseArea {
                        anchors.fill: parent; anchors.margins: -6
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (typeof bridge.resetParam === "function") bridge.resetParam(modelData.name)
                    }
                }
            }
        }
    }
}
