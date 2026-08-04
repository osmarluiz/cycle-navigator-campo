# -*- coding: utf-8 -*-
"""Folha de estilo da janela. Separada do app so' para o app ficar legivel."""
QSS = """
QWidget { background:#15170f; color:#e8e6d8; font-size:13px; }
QLabel#title { font-size:19px; font-weight:700; color:#f2f0e2; }
QLabel#sub { color:#9a9c8c; font-size:11px; }
QLabel#hd  { color:#cfe3b0; font-weight:600; margin-top:2px; }
QLabel#hr  { background:#2b2e22; }
QLabel#info { color:#c9c7ba; font-size:11px; background:#1c1f15; border-radius:6px; padding:7px; }
QLabel#bignum { font-size:30px; font-weight:800; color:#a7d06a; }
QWidget#topbar { background:#1c1f15; border-bottom:1px solid #2b2e22; }
QComboBox, QPushButton { background:#232619; border:1px solid #333726; border-radius:7px; padding:6px 10px; }
QComboBox:hover, QPushButton:hover { border-color:#5a6b3a; }
QComboBox QAbstractItemView { background:#232619; selection-background-color:#3f5426; }
QPushButton#cta { background:#3f6b2a; border:1px solid #5a8f38; font-weight:600; padding:9px; }
QPushButton#cta:hover { background:#4c8232; }
QRadioButton, QCheckBox { spacing:6px; }
QSlider::groove:horizontal { height:5px; background:#2b2e22; border-radius:2px; }
QSlider::handle:horizontal { width:15px; margin:-6px 0; border-radius:8px; background:#a7d06a; }
QSlider::handle:horizontal:disabled { background:#3a3d2c; }
QSlider::sub-page:horizontal { background:#5a8f38; border-radius:2px; }
QSplitter::handle { background:#22251a; }
"""
