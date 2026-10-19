# tools — preparo dos dados de referência

Scripts que rodam **uma vez**, fora do programa, para produzir as camadas de referência que o
navegador carrega de `<aoi>/car/` e `<aoi>/sam/`. Dependem de ambientes próprios (SICAR + Tesseract;
SAM 2 + CUDA) e de caminhos desta máquina — ajuste as constantes no topo de cada um.

| script | faz | ambiente |
|---|---|---|
| `car_baixa.py DF GO MG` | baixa a camada AREA_IMOVEL do SICAR por estado, resolvendo o captcha por OCR | `pip install git+https://github.com/urbanogilson/SICAR` + Tesseract |
| `car_recorta.py` | junta os estados, recorta pelo retângulo do AOI (interseção), remove duplicata de divisa → `car_aoi.gpkg` | geopandas |
| `sam_sonda.py` | um tile pelo SAM 2.1: tempo e cara das máscaras, antes de gastar uma hora | sam2 + torch/CUDA |
| `sam_segmenta.py` | o AOI inteiro em tiles de 1024 com sobreposição; filtra, deduplica, junta → `sam_aoi.gpkg` | sam2 + torch/CUDA |
