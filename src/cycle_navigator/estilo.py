# -*- coding: utf-8 -*-
"""O SISTEMA DE DESIGN: tokens, tipografia e estados -- um lugar so'.

⚠️⚠️ TOKENS, NAO HEXADECIMAIS SOLTOS. A versao anterior tinha vinte cores escritas a mao em tres
arquivos, e nenhuma delas combinava por intencao: eram parecidas por acaso. Aqui ha' quatro
superficies, tres tons de texto, UM acento para acao e UM para selecao, e os estados (hover,
pressionado, marcado, foco, desabilitado) derivam deles. Trocar a identidade e' trocar oito linhas.

⚠️ A FONTE E' A DO SISTEMA. O Qt abre em "Sans Serif 9pt" generica, que no Windows cai numa fonte de
fallback sem hinting -- e' o que da' a cara de ferramenta improvisada. Segoe UI Variable e' a fonte
do proprio Windows 11: o usuario ja' a le' o dia inteiro, ela tem tamanhos opticos, e renderiza
nitida em 96 dpi. Tamanhos em PIXEL, nao em ponto, para o layout nao mudar de maquina para maquina.

⚠️ ALVOS DE 32 PX. Em campo se usa trackpad, ou um mouse apoiado no joelho. Botao de 24 px e' alvo
de escritorio.
"""
import pathlib

from PyQt6.QtGui import QFont, QFontDatabase, QIcon

# ⚠️ a seta do combo e' um SVG de verdade. O QSS do Qt nao desenha triangulo por borda num
# subcontrole sem tamanho: o resultado era um quadradinho em todo combo da tela.
CHEVRON = (pathlib.Path(__file__).parent / "_icones" / "chevron.svg").as_posix()
# icone da janela/Dock/barra de tarefas; gerado de build/icone/icone.svg por build/icone/gera_icones.py
ICONE_APP = (pathlib.Path(__file__).parent / "_icones" / "app.png").as_posix()

# ---------------- tokens ----------------
BG = "#121410"          # fundo da janela
PANEL = "#1a1d14"       # barras e paineis
RAISED = "#22261a"      # controles em repouso
HOVER = "#2a2f20"       # controle sob o mouse
BORDER = "#2f3425"
BORDER_STRONG = "#454c36"

TEXT = "#ecebe0"
TEXT_2 = "#a9ac9c"      # rotulos de campo, legendas
TEXT_3 = "#8f9383"      # dicas, estados vazios (4,5:1 sobre PANEL e RAISED: o minimo para ler)

ACCENT = "#8fc452"      # a acao primaria (Gravar, modo ativo)
ACCENT_HOVER = "#a1d463"
ACCENT_DOWN = "#7bab45"
ON_ACCENT = "#101308"

FOCO = "#00e5ff"        # a selecao na CURVA (faixa em foco) -- nao confundir com acao
PERIGO = "#d9534f"

FONTE = "Segoe UI Variable Text"
FONTE_ALT = "Segoe UI"
MONO = "Cascadia Code"

# superficies flutuantes sobre o mapa (ferramentas, dica, aviso): o PANEL com transparencia, para o
# mapa continuar lido por baixo
FLUTUA = "rgba(26,29,20,232)"


def fonte_do_sistema():
    """Segoe UI no Windows; no Mac (e no resto) a fonte de interface do proprio sistema.

    ⚠️ No Mac a Segoe nao existe: o Qt procurava "Segoe UI Variable Text", nao achava, gastava tempo
    montando aliases (aviso "Populating font family aliases" no log) e caia numa sans generica.
    A fonte do sistema (SF Pro) e' a que o usuario do Mac le' o dia inteiro -- mesma logica que
    escolheu a Segoe no Windows.
    """
    for fam in (FONTE, FONTE_ALT):
        if fam in QFontDatabase.families():
            return fam
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()


def aplica(app):
    """Fonte do sistema + folha de estilo + icone. Chamar uma vez, logo depois do QApplication."""
    app.setWindowIcon(QIcon(ICONE_APP))
    fam = fonte_do_sistema()
    f = QFont(fam)
    f.setPixelSize(14)
    app.setFont(f)
    app.setStyleSheet(qss(fam))


def qss(fonte=FONTE):
    return _QSS.replace("__FONTE__", fonte)


_QSS = f"""
* {{ font-family: "__FONTE__", sans-serif; }}
QWidget {{ background:{BG}; color:{TEXT}; font-size:14px; }}
QToolTip {{ background:{RAISED}; color:{TEXT}; border:1px solid {BORDER_STRONG};
            padding:6px 8px; border-radius:6px; font-size:12px; }}

/* ---------- tipografia ---------- */
QLabel {{ background:transparent; }}
QLabel#h1 {{ font-size:18px; font-weight:600; color:{TEXT}; }}
QLabel#h2 {{ font-size:15px; font-weight:600; color:{TEXT}; }}
QLabel#rotulo {{ font-size:12px; font-weight:600; color:{TEXT_2};
                 text-transform:uppercase; letter-spacing:0.5px; }}
QLabel#dica {{ font-size:12px; color:{TEXT_3}; }}
QLabel#vazio {{ font-size:15px; color:{TEXT_3}; }}
QLabel#contador {{ font-size:13px; color:{TEXT_2}; }}
/* cartao flutuante sobre o mapa (imovel do CAR selecionado) */
QLabel#card {{ background:rgba(18,20,16,235); color:{TEXT}; border:1px solid {BORDER_STRONG};
               border-radius:10px; padding:10px 12px; font-size:12px; }}

/* ---------- superficies ---------- */
QWidget#topbar {{ background:{PANEL}; border-bottom:1px solid {BORDER}; }}
QWidget#rodape {{ background:{PANEL}; border-top:1px solid {BORDER}; }}
QFrame[frameShape="5"] {{ color:{BORDER_STRONG}; max-width:1px; margin:4px 6px; }}
QSplitter::handle {{ background:{BORDER}; }}
QSplitter::handle:hover {{ background:{BORDER_STRONG}; }}
QSplitter::handle:vertical {{ height:5px; }}
QSplitter::handle:horizontal {{ width:5px; }}

/* ---------- botoes ---------- */
QPushButton, QToolButton {{
    background:{RAISED}; color:{TEXT}; border:1px solid {BORDER};
    border-radius:8px; min-height:32px; font-weight:500; }}
QPushButton {{ padding:0 14px; }}
QToolButton {{ padding:0 6px; }}   /* os botoes de zoom do mapa sao 32x32 fixos: padding largo os esmaga */
QPushButton:hover, QToolButton:hover {{ background:{HOVER}; border-color:{BORDER_STRONG}; }}
QPushButton:pressed, QToolButton:pressed {{ background:{PANEL}; }}
QPushButton:focus, QToolButton:focus {{ border:1px solid {ACCENT}; }}
QPushButton:disabled, QToolButton:disabled {{ color:{TEXT_3}; background:{PANEL};
                                             border-color:{BORDER}; }}
QToolButton::menu-indicator {{ image:none; width:0; }}

/* acao primaria: um unico botao cheio por tela */
QPushButton#cta {{ background:{ACCENT}; color:{ON_ACCENT}; border:1px solid {ACCENT};
                   font-weight:600; padding:0 20px; }}
QPushButton#cta:hover {{ background:{ACCENT_HOVER}; border-color:{ACCENT_HOVER}; }}
QPushButton#cta:pressed {{ background:{ACCENT_DOWN}; }}
QPushButton#cta:disabled {{ background:{RAISED}; color:{TEXT_3}; border-color:{BORDER}; }}

/* botao discreto: borda so' no hover */
QPushButton#ghost, QToolButton#ghost {{ background:transparent; border-color:transparent; }}
QPushButton#ghost:hover, QToolButton#ghost:hover {{ background:{HOVER}; border-color:{BORDER}; }}

/* controle segmentado dos modos: o marcado e' o aceso */
/* sem mudar o peso da fonte no estado marcado: o Qt mede a largura com o peso normal, e o texto
   em negrito nao cabe mais ("Identifica"). A cor cheia ja' diz qual esta' ativo. */
QPushButton#modo {{ border-radius:8px; padding:0 16px; }}
QPushButton#modo:checked {{ background:{ACCENT}; color:{ON_ACCENT}; border-color:{ACCENT}; }}
QPushButton#modo:checked:hover {{ background:{ACCENT_HOVER}; }}

/* as abas do painel do lugar: Pixel | Fazenda */
QPushButton#aba {{ background:transparent; border:none; border-bottom:2px solid transparent;
                   border-radius:0; color:{TEXT_2}; padding:4px 12px 6px 10px; font-weight:600; }}
QPushButton#aba:hover {{ color:{TEXT}; }}
QPushButton#aba:checked {{ color:{TEXT}; border-bottom-color:{ACCENT}; }}

/* a lista das faixas, ao lado da curva */
QFrame#faixa_linha {{ border:1px solid transparent; border-radius:8px; min-height:26px; }}
QFrame#faixa_linha:hover {{ background:{HOVER}; }}
QFrame#faixa_linha[aceso="true"] {{ background:{RAISED}; border-color:{FOCO}; }}
QLabel#faixa_periodo {{ color:{TEXT_2}; font-size:12px; }}
QToolButton#faixa_x {{ border:none; background:transparent; min-width:24px; max-width:24px; min-height:24px; }}
QToolButton#faixa_x:hover {{ background:{HOVER}; border-radius:6px; }}

/* perigo */
QPushButton#perigo:hover {{ border-color:{PERIGO}; color:{PERIGO}; }}

/* ---------- campos ---------- */
QComboBox, QLineEdit, QPlainTextEdit {{
    background:{RAISED}; color:{TEXT}; border:1px solid {BORDER};
    border-radius:8px; padding:0 10px; min-height:32px; selection-background-color:{ACCENT};
    selection-color:{ON_ACCENT}; }}
QPlainTextEdit {{ padding:6px 10px; }}
QComboBox:hover, QLineEdit:hover, QPlainTextEdit:hover {{ border-color:{BORDER_STRONG}; }}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {{ border:1px solid {ACCENT}; }}
QComboBox:disabled, QLineEdit:disabled {{ color:{TEXT_3}; background:{PANEL}; }}
QComboBox::drop-down {{ border:none; width:26px; }}
QComboBox::down-arrow {{ image:url({CHEVRON}); width:12px; height:12px; margin-right:8px; }}
QComboBox QAbstractItemView {{ background:{RAISED}; border:1px solid {BORDER_STRONG};
                               selection-background-color:{HOVER}; selection-color:{TEXT};
                               padding:4px; outline:0; }}
QComboBox QAbstractItemView::item {{ min-height:28px; padding:0 8px; border-radius:6px; }}
QLineEdit[placeholderText] {{ color:{TEXT}; }}

/* ---------- sliders ---------- */
QSlider::groove:horizontal {{ height:4px; background:{BORDER}; border-radius:2px; }}
QSlider::sub-page:horizontal {{ background:{ACCENT}; border-radius:2px; }}
QSlider::handle:horizontal {{ width:16px; height:16px; margin:-6px 0; border-radius:8px;
                              background:{TEXT}; border:2px solid {ACCENT}; }}
QSlider::handle:horizontal:hover {{ background:#ffffff; }}

/* ---------- tabelas ---------- */
QTableWidget, QTableView {{ background:{BG}; alternate-background-color:{PANEL};
    gridline-color:{BORDER}; border:1px solid {BORDER}; border-radius:8px;
    selection-background-color:#2e4a1e; selection-color:{TEXT}; outline:0; }}
QTableWidget::item {{ padding:0 8px; min-height:30px; border:none; }}
QTableWidget::item:hover {{ background:{HOVER}; }}
QHeaderView::section {{ background:{PANEL}; color:{TEXT_2}; font-size:12px; font-weight:600;
    padding:8px; border:none; border-bottom:1px solid {BORDER_STRONG};
    border-right:1px solid {BORDER}; }}
QTableCornerButton::section {{ background:{PANEL}; border:none; }}

/* ---------- abas ---------- */
QTabWidget::pane {{ border:none; top:-1px; }}
QTabBar::tab {{ background:transparent; color:{TEXT_2}; padding:10px 18px; border:none;
                border-bottom:2px solid transparent; font-weight:500; }}
QTabBar::tab:hover {{ color:{TEXT}; }}
QTabBar::tab:selected {{ color:{TEXT}; border-bottom:2px solid {ACCENT}; }}

/* ---------- menus e dialogos ---------- */
QMenu {{ background:{RAISED}; border:1px solid {BORDER_STRONG}; border-radius:8px; padding:8px; }}
QMenu::item {{ padding:8px 14px; border-radius:6px; }}
QMenu::item:selected {{ background:{HOVER}; }}
QDialog {{ background:{PANEL}; }}
QDialogButtonBox QPushButton {{ min-width:96px; }}

/* ---------- barras de rolagem ---------- */
QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{BORDER_STRONG}; border-radius:4px; min-height:24px; }}
QScrollBar::handle:vertical:hover {{ background:{TEXT_3}; }}
QScrollBar:horizontal {{ background:transparent; height:10px; margin:2px; }}
QScrollBar::handle:horizontal {{ background:{BORDER_STRONG}; border-radius:4px; min-width:24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
QCheckBox, QRadioButton {{ spacing:8px; }}

/* ---------- barra de cima ---------- */
/* ---------- analise ---------- */
QFrame#cartao {{ background:{PANEL}; border:1px solid {BORDER}; border-radius:12px; }}
QLabel#numero {{ font-size:30px; font-weight:600; color:{TEXT}; }}
QLabel#numero[alerta="true"] {{ color:#e0a23a; }}
QPushButton#linha {{ background:transparent; border:1px solid transparent; border-radius:8px;
                     text-align:left; }}
QPushButton#linha:hover {{ background:{HOVER}; border-color:{BORDER}; }}
QLabel#marca {{ font-size:15px; font-weight:600; color:{TEXT}; }}
QLineEdit#busca {{ border-radius:16px; padding-left:34px; background:{RAISED}; }}
QPushButton#contagem {{ background:{RAISED}; color:{TEXT_2}; border:1px solid {BORDER};
                        border-radius:10px; padding:4px 12px; font-size:12px; font-weight:600;
                        min-height:0; }}
QPushButton#contagem:hover {{ background:{HOVER}; color:{TEXT}; border-color:{ACCENT}; }}

/* ---------- sobre o mapa ---------- */
QWidget#flutuante {{ background:{FLUTUA}; border:1px solid {BORDER_STRONG}; border-radius:12px; }}
QWidget#flutuante QPushButton {{ background:transparent; border:1px solid transparent;
                                 border-radius:8px; padding:0 12px; }}
QWidget#flutuante QPushButton:hover {{ background:{HOVER}; border-color:{BORDER}; }}
QWidget#flutuante QPushButton:checked {{ background:{ACCENT}; color:{ON_ACCENT}; border-color:{ACCENT}; }}
QWidget#flutuante QPushButton#camada:checked {{ background:rgba(143,196,82,95); color:{TEXT};
                                                border:2px solid {ACCENT}; }}
QLabel#pilula {{ background:{FLUTUA}; color:{TEXT_2}; border:1px solid {BORDER};
                 border-radius:12px; padding:5px 14px; font-size:12px; }}
QLabel#aviso {{ background:{ACCENT}; color:{ON_ACCENT}; border-radius:15px; padding:8px 20px;
                font-size:13px; font-weight:600; }}
QLabel#aviso[tipo="erro"] {{ background:{PERIGO}; color:#ffffff; }}
QLabel#aviso[tipo="info"] {{ background:{RAISED}; color:{TEXT}; border:1px solid {BORDER_STRONG}; }}

/* ---------- painel do ciclo ---------- */
QLabel#passo {{ color:{TEXT_2}; font-size:14px; }}
QLabel#num {{ background:{RAISED}; color:{ACCENT}; border:1px solid {BORDER_STRONG};
              border-radius:13px; min-width:26px; max-width:26px; min-height:26px; max-height:26px;
              font-weight:700; font-size:13px; qproperty-alignment:AlignCenter; }}
QLabel#titulo {{ font-size:15px; font-weight:600; color:{TEXT}; }}
QLabel#subtitulo {{ color:{TEXT_2}; font-size:12px; }}

/* controle segmentado: botoes encostados, o marcado aceso */
QWidget#seg {{ background:{RAISED}; border:1px solid {BORDER}; border-radius:9px; }}
QWidget#seg QPushButton {{ background:transparent; border:none; border-radius:7px; min-height:26px;
                           padding:0 12px; color:{TEXT_2}; font-size:13px; }}
QWidget#seg QPushButton:hover {{ color:{TEXT}; background:{HOVER}; }}
QWidget#seg QPushButton:checked {{ background:{BORDER_STRONG}; color:{TEXT}; }}
QWidget#seg QPushButton:disabled {{ color:{TEXT_3}; }}

/* culturas de um clique */
QPushButton#cultura {{ border-radius:15px; min-height:30px; padding:0 12px 0 10px; font-size:13px; }}
QPushButton#cultura:checked {{ background:{HOVER}; border:1px solid {TEXT_2}; color:{TEXT}; }}
"""


QSS = qss()          # compatibilidade: quem importava a folha pronta continua funcionando
