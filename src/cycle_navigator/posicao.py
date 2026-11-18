# -*- coding: utf-8 -*-
"""ONDE ESTOU: a posicao do computador, quando o sistema souber dizer.

⚠️ NOTEBOOK NAO TEM GPS. O Mac e o Windows estimam a posicao pelas redes Wi-Fi ao redor; no meio da
lavoura, sem rede nenhuma, o sistema pode nao responder. Por isso a falha aqui e' um recado, nunca um
erro -- e o recado ensina o caminho que sempre funciona: colar na busca a coordenada do celular.

⚠️ OPCIONAL DE PONTA A PONTA. Sem o modulo QtPositioning, sem permissao, sem resposta em 15 s: recado.
No Mac a permissao so' pode ser pedida por um .app com NSLocationWhenInUseUsageDescription no
Info.plist (o spec do PyInstaller poe); rodando do codigo o sistema nega sem perguntar.
"""
import logging

from PyQt6.QtCore import QCoreApplication, QObject, Qt, pyqtSignal

log = logging.getLogger(__name__)

SEM = "Sem localização do sistema — cole na busca a coordenada do celular (-15.79, -47.88)"


class OndeEstou(QObject):
    achou = pyqtSignal(float, float, float)      # lat, lon, precisao em metros (ou -1)
    falhou = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fonte = None

    def pede(self):
        try:
            from PyQt6.QtCore import QLocationPermission
            app = QCoreApplication.instance()
            perm = QLocationPermission()
            perm.setAccuracy(QLocationPermission.Accuracy.Precise)
            st = app.checkPermission(perm)
            if st == Qt.PermissionStatus.Undetermined:
                app.requestPermission(perm, lambda p: self._respondeu(p))
                return
            if st == Qt.PermissionStatus.Denied:
                self.falhou.emit("Localização não autorizada (Ajustes → Privacidade → Serviços de "
                                 "Localização) — ou cole a coordenada na busca")
                return
        except Exception as e:                    # Qt sem a API de permissao: tenta direto
            log.info("permissao de localizacao indisponivel (%s)", e)
        self._comeca()

    def _respondeu(self, perm):
        if perm.status() == Qt.PermissionStatus.Granted:
            self._comeca()
        else:
            self.falhou.emit(SEM)

    def _comeca(self):
        try:
            from PyQt6.QtPositioning import QGeoPositionInfo, QGeoPositionInfoSource
            if self._fonte is None:
                self._fonte = QGeoPositionInfoSource.createDefaultSource(self)
                if self._fonte is None:
                    self.falhou.emit(SEM)
                    return
                self._fonte.positionUpdated.connect(self._chegou)
                self._fonte.errorOccurred.connect(lambda *_: self.falhou.emit(SEM))
            self._attr = QGeoPositionInfo.Attribute.HorizontalAccuracy
            self._fonte.requestUpdate(15000)
        except Exception as e:
            log.info("localizacao indisponivel (%s): %s", type(e).__name__, e)
            self.falhou.emit(SEM)

    def _chegou(self, info):
        c = info.coordinate()
        if not c.isValid():
            self.falhou.emit(SEM)
            return
        prec = info.attribute(self._attr) if info.hasAttribute(self._attr) else -1.0
        self.achou.emit(c.latitude(), c.longitude(), float(prec))
