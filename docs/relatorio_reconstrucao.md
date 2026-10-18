# Reconstrução do LabSEA — revisão de 15/10/2026, referência de 14/10/2026

## Referências e escopo

A reconstrução utiliza `saida/imagens_reais/20261014_141328`, capturada pelo usuário via IS-Wire. Os timestamps de origem vão de **17:13:29.654510 a 17:13:29.722079 UTC**: intervalo de **67,57 ms**. Foram examinadas as quatro imagens originais e as quatro versões corrigidas com ROI. A cena e seus renders foram atualizados em **18/10/2026**; as comparações atuais estão em `saida/comparacoes/final_20261018/`.

As imagens reais substituem a limitação da etapa anterior, quando o broker não estava acessível neste ambiente. A captura existente foi preservada; não foi necessário capturar outro estado do laboratório.

Entradas inspecionadas: os modelos Blender existentes, scripts de criação/aberturas/render, configurações J21/P6/J16 e os quatro NPZ. As calibrações contêm `cam_id`, `K`, `nK`, `dist`, `roi`, `rt`, `rt_inv`, `P_original`, `P_undistorted`, `height`, `width` e `escala`. Todas indicam **1280 × 720 px**. `rt` representa mundo → câmera OpenCV; `rt_inv` é a transformação inversa.

## Arquitetura, câmeras e forro

Durante a reconstrução, a entrada arquitetônica foi `modelos/labsea_com_aberturas.blend` e a saída foi `modelos/labsea_reconstruido.blend`. Malhas, faces, modificadores de aberturas e matrizes dos objetos originais foram comparados antes/depois, com a revisão explícita do pilar descrita abaixo. Materiais, UV do piso e organização em coleções foram atualizados. Para simplificar a entrega, os `.blend` intermediários foram removidos; o arquivo distribuído é o modelo final.

| Elemento | Estado |
| --- | --- |
| Sala | 6,95 × 8,67 m, conforme o `.blend` original |
| Paredes | 3,70 m, sem redimensionamento |
| Piso | Superfície em Z = 0, mesma geometria |
| J21/J16/P6 | Aberturas e posições preservadas |
| Pilares | Dois pilares de 0,52 m; `Pilar_J21` recebeu revisão provisória de +0,05 m em X |
| Forro | Superfície adicional a **2,97 m**, hipótese com confiança baixa |

A largura textual de **6,67 m** diverge dos **6,95 m** do arquivo. A largura permanece sem alteração. O afastamento da J21 esquerda ao pilar era **0,03 m**; a descrição inicial citava 0,06 m. Em 15/10 o usuário esclareceu que a posição do pilar veio apenas da planta, estima **0,08 m** entre o fim da janela esquerda e o pilar e confirma que as mesas de 0,80 + 1,60 + 0,80 m cabem integralmente no vão. Foi aplicada uma **revisão provisória de +0,05 m em X somente no Pilar_J21**, resultando em 0,08 m de folga à janela esquerda e 3,215 m de vão para as mesas. Essa inferência tem **confiança baixa e requer medição**. A janela direita foi preservada; o encontro de sua moldura com o pilar passou a ter 0,02 m de sobreposição em projeção X e também requer conferência. A posição anterior e a revisão estão documentadas neste relatório e em `architecture_adjustments` em `objects.json`; todas as demais transformações arquitetônicas permanecem iguais.

Os centros ópticos calibrados têm Z entre **2,8425 e 2,8851 m**. O usuário confirmou fixação das câmeras no teto. Por isso foi acrescentado um forro separado e as bases visuais das câmeras passaram a ser horizontais. A altura de 2,97 m **não foi medida nem triangulada**. O espaçamento interno entre lente, carcaça e forro permanece aproximado. As paredes acima do forro continuam presentes.

As dimensões nominais da VIP 1230 D G2 — **85,5 mm de altura e 109 mm de diâmetro** — vêm da [ficha técnica oficial Intelbras](https://backend.intelbras.com/sites/default/files/2022-07/Datasheet%20UNIFICADO%20-%20VIP%201230%20B.D.G2%20%28VERSAO%205%29_0.pdf). Base, aro, corpo dome, lente e espaçador são peças visuais separadas. O espaçador não integra a dimensão nominal do equipamento. A carcaça da câmera ativa é ocultada durante seu render; as outras permanecem visíveis.

### Projeção salva no Blender

O arquivo de entrada armazenava lentes padrão de **50 mm**, com deslocamentos nulos. O renderizador anterior já aplicava `nK` em tempo de execução. A nova cópia passou a armazenar explicitamente **essa mesma projeção calibrada**, com lente calculada, deslocamentos de principal point e metadados do aspecto de pixel. Isso não altera os NPZ, nem as posições/orientações das câmeras.

O Blender usa câmera local olhando para −Z; a conversão da rotação OpenCV é `R_wc @ diag(1, −1, −1)`. O mundo continua métrico, Z para cima. Cada render configura seu próprio aspecto de pixel. Comparações usam o ROI correspondente, sem deslocamento ou ajuste manual do enquadramento.

## Inventário e posicionamento

`scene_data/objects.json` registra IDs, tipos, posições, rotações em graus, dimensões, confiança, fontes e hipóteses. `docs/inventario.csv` fornece uma versão tabular. O inventário tem **74 raízes**, além da arquitetura e dos detalhes gerados de piso/parede/forro.

| Grupo | Quantidade modelada | Evidência / aproximação |
| --- | ---: | --- |
| Bancadas laterais | 11 módulos | Leste, oeste e parede das janelas; divisão dos módulos parcialmente estimada |
| Mesa em L | 1 | Dois cantos triangulados; recorte, saia e apoios estimados |
| Mesa de reunião | 1 | Tampo circular, posição/silhueta conferidas nas quatro vistas |
| Cadeiras | 13 | 12 de escritório e uma verde; posições transitórias da captura |
| Armários altos | 3 | Volumes distintos vistos junto à entrada e à parede oeste |
| Monitores / televisor | 13 + 1 | Telas, pés e cabos; periféricos parcialmente oclusos |
| Gabinetes | 1 | Volume/equipamento no canto tem confiança baixa |
| Impressoras 3D | 2 | Uma estrutura aberta e uma GTMax Core A2V2 identificada pelo usuário |
| Teclados com mouse | 9 conjuntos | Simplificações de estações observadas, sem inferir periféricos ocultos |
| Quadro branco / avisos | 1 + 1 | Posições e molduras; escrita/fotos simplificadas |
| Projetor | 1 | Correspondência conferida nas vistas 2, 3 e 4 |
| Outros acessórios | 13 | Escada, painel dobrado, lixeira, nichos, caixas, maleta, copo e objeto laranja |
| Câmeras físicas | 4 | Origem óptica calibrada e montagem aproximada no forro |

As cadeiras têm raízes `Chair_001` a `Chair_013`, origem no piso, escala unitária e filhos com coordenadas locais. Foram incluídos assento, encosto, suporte, pistão, base com cinco raios, rodízios e braços quando identificados. A cadeira verde tem estrutura fixa independente. Os IDs são estáveis no modelo; a associação de identidade entre capturas ainda depende do futuro rastreamento.

Os tampos têm espessura, estrutura metálica, pés e saias. Um gaveteiro observado foi incluído na bancada oeste. A mesa em L usa uma malha com recorte côncavo. Nenhuma bancada central antiga foi reconstruída: suas marcas foram representadas apenas na superfície do piso.

### Medidas corrigidas com o usuário (15/10)

As cinco mesas leste, as duas oeste e as mesas centrais sob ambas as janelas têm **1,60 m de largura**, conforme confirmação do usuário. A bancada sob a janela esquerda foi separada em três objetos: **0,80 + 1,60 + 0,80 m**, com as duas mesas menores alinhadas com a central. Seus IDs são `Desk_North_03`, `Desk_North_01` e `Desk_North_04`, respectivamente. A profundidade das menores foi informada apenas como inferior à das grandes: foram adotados provisoriamente **0,50 m**, contra **0,70 m** nas grandes sob as janelas. Os módulos menores estão na mesma orientação e com a frente 0,10 m recuada em relação à mesa central; esse recuo acomoda a bancada perpendicular e ainda é uma estimativa. Essas profundidades ainda precisam de medição.

A sobreposição anterior de **0,26 m** entre `Desk_West_01` e `Cabinet_002` foi eliminada pelo reposicionamento das mesas oeste. As cadeiras editadas pelo usuário permanecem nas mesmas poses. A mesa de reunião e o copo foram afastados 0,12 m da janela para acomodar o módulo menor; sua posição permanece aproximada. O gabinete no canto foi separado da impressora 3D, e o monitor junto ao armário recebeu deslocamento de 0,06 m.

A imagem local `mesas_marcadas.png` foi registrada na imagem original da câmera 3 por correspondências SIFT (109 inliers). A homografia deste registro transforma somente o recorte ampliado para a **mesma imagem original**. Depois foram aplicados `undistortPoints`, o ROI e interseções de raios com **Z = 0,75 m**. Não foi aplicada uma homografia de piso aos tampos. As observações e a transformação estão em `scene_data/desk_observations.json`.

### Identificação da impressora sob a TV

O usuário identificou o objeto antes chamado `Computer_001` como uma **GTMax Core A2V2**. Ele foi substituído por `Printer3D_002`, com `legacy_id` registrado, estrutura de aço escura, porta e tampa transparentes, mesa de impressão, guias, cabeçote, LCD, seletor e rótulos simplificados. A impressora aberta `Printer3D_001` sob a janela foi mantida separadamente. A posição da GTMax foi corrigida para (3,10; −2,14; 0,75) m, conferindo a tampa nas câmeras 3 e 4; a posição herdada do gabinete estava deslocada em 0,59 m ao longo da bancada. Monitor e teclado vizinhos receberam pequenos afastamentos para acomodar o envelope correto.

O envelope adotado é **0,425 × 0,470 × 0,512 m** (L × P × A), conforme a proposta do fabricante reproduzida no [relatório institucional do IFC](https://acessoainformacao.ifc.edu.br/wp-content/uploads/sites/26/2022/10/Relatorio-Consolidado-OS-005_2020_revisado_Unai-IFC.odt_RGR.pdf). A disposição visual foi conferida na captura do laboratório e em [fotografia do equipamento](https://pr.olx.com.br/regiao-de-londrina/informatica/perifericos-de-computador/impressora-3d-gtmax-core-a2v2-em-otimo-estado-1459327545). As posições internas e espessuras são aproximações, sem pretensão de modelo mecânico. Fotografias externas não foram usadas como texturas nem incluídas no repositório.

### Geometria multivista

Foram geradas projeções de diagnóstico sobre Z = 0 e Z = 0,75 m. Elas não confundem tampos ou encostos com pontos do chão. As anotações vivem em coordenadas da imagem corrigida/ROI; o deslocamento do ROI é reposto antes de construir cada raio.

Dois cantos do tampo em L foram identificados nas vistas 2, 3 e 4. A triangulação produziu aproximadamente:

- Canto noroeste: **(0,358; −2,753; 0,751) m**.
- Canto nordeste: **(1,936; −2,744; 0,748) m**.

O modelo usa Z = 0,75 m e os cantos (0,357; −2,750) e (1,937; −2,750). O erro RMS das seis observações usadas no ajuste é **2,83 px**. Dois pontos correspondentes na câmera 1, separados do ajuste, apresentam RMS de **4,26 px**. A incerteza de anotação manual foi estimada em 5 px. Essa verificação cobre **dois cantos da mesa**, não certifica todo o mobiliário.

Para as cadeiras foram usados pontos dos assentos em Z ≈ 0,46 m e, quando ocultos, encostos ou contato com a bancada. São estimativas de confiança média, sujeitas à escolha do ponto, à altura presumida e à mobilidade. O projetor inicialmente pareceu ocupar duas posições; a comparação multivista mostrou tratar-se de um único objeto e a duplicação foi removida.

## Materiais e iluminação

- Granilite procedural com textura determinística de 1 m, fragmentos milimétricos, UV em escala mundial, rugosidade e relevo sutis. A imagem fica empacotada no `.blend` e no GLB.
- Juntas entre placas, marcas residuais e alvos de piso. Espaçamento e desgaste são aproximações visuais, não um levantamento de cada junta.
- Paredes pintadas, faixa de pastilhas verdes, laminados claros, metal, tecido/plástico das cadeiras, telas escuras e cortiça do quadro.
- Vidros com transmissão moderada. A radiância difusa aproxima a vista exterior clara; a paisagem externa não foi reconstruída.
- Cycles, gerenciamento AgX, iluminação natural pelas janelas e fontes artificiais estimadas. Não foram inventadas malhas de luminárias cuja quantidade/posição não ficou legível nas imagens.

O material do piso recebeu um fator de 0,82 nos valores sRGB da textura procedural. As exposições finais são −0,60 EV (câmera 1), −0,55 EV (2), −0,95 EV (3) e −1,00 EV (4), estimadas nas regiões centrais do piso da mesma captura. Esses valores simulam diferenças aparentes de exposição; não são metadados medidos nem calibração radiométrica. Portanto, as métricas de cor nessa região participam do ajuste e não constituem validação independente.

As potências de luz e os materiais são ajustados por comparação, não medidos. Os originais têm saturação nas janelas e processamento interno das câmeras; a resposta fotométrica completa dessas câmeras não foi calibrada. O resultado ainda pode divergir em sombras, cor, contraste e reflexos.

## Implementação e organização

O código foi separado em `primitives.py`, `furniture.py`, `electronics.py`, `materials.py`, `camera_models.py`, `lighting.py` e `scene_builder.py`. Os modelos físicos das câmeras são criados junto com a cena final. A criação de malhas evita operadores de seleção para reduzir o custo de reconstrução.

A hierarquia `LabSEA` separa `Architecture`, `Furniture`, `DynamicObjects/Chairs`, `Electronics`, `WallObjects`, `Cameras/RenderCameras`, `Cameras/CameraModels` e `Lighting`. O builder remove somente objetos que ele próprio marcou como gerados. Reexecuções não duplicam as raízes.

Na retomada de 15/10 foi detectada uma edição posterior do Blender: `Chair_008`, `Chair_012` e `Chair_013` tinham novas posições, e os antigos marcadores foram substituídos por 77 cruzes em grade. Essas alterações foram preservadas no modelo final. As poses atuais foram sincronizadas em `objects.json`; a malha, posição e escala das cruzes foram registradas em `scene_data/floor_markers.json`. A grade branca provém do arquivo recebido, não de uma nova inferência das fotos.

O repositório contém a cena final, scripts, dados e documentação. Os `.blend` intermediários, backups, prévias e diagnósticos temporários foram removidos. Capturas reais, renders, comparações e o GLB permanecem em `saida/`, ignorada pelo Git.

## Validações e artefatos

Os resultados quantitativos finais, a comparação com o modelo vazio e as limitações específicas das quatro vistas estão na seção a seguir e em `docs/validacao_resumo.json`.

### Comparação final das quatro câmeras

Os quatro renders foram efetivamente gerados em **1280 × 720, Cycles, 32 amostras** e comparados com as referências corrigidas no ROI de cada câmera. A tabela compara o modelo arquitetônico sem mobiliário com esta revisão. F1 de bordas usa tolerância de 3 px; MAE é o erro médio de cor em escala 0–255. Essas métricas são auxiliares e **não representam percentual de fidelidade geométrica**.

| Câmera | F1 inicial → atual | MAE inicial → atual | Mediana do piso real / sintético |
| --- | ---: | ---: | ---: |
| 1 | 0.041 → 0.566 | 59.1 → 42.5 | 145 / 136 |
| 2 | 0.072 → 0.589 | 61.9 → 36.8 | 149 / 140 |
| 3 | 0.102 → 0.626 | 63.4 → 40.2 | 136 / 115 |
| 4 | 0.086 → 0.584 | 52.9 → 49.4 | 136 / 116 |

### Verificações executadas

- As quatro poses calibradas e os NPZ foram preservados. Erro máximo da projeção Blender/OpenCV: **0,000192 px** nos pontos de teste; isso valida a conversão matemática, não a precisão da calibração física.
- Malhas arquitetônicas preservadas; transformações idênticas salvo a revisão explícita `Pilar_J21`.
- **13 cadeiras** movimentadas individualmente durante teste e restauradas; filhos acompanham a raiz sem mover os demais objetos.
- **406 matrizes** das cadeiras, peças e markers preservadas exatamente durante a reconstrução; **77 markers** também conferidos por vértices, faces, posição, rotação e escala.
- **216 pares** de volumes em planta verificados sem interseção entre tampos, corpos de armários, paredes e pilares. O teste usa retângulos orientados e polígono circular; não certifica cada cabo, rodízio ou detalhe de malha.
- Reexecução do builder: **74 raízes e 4.016 objetos**, sem aumento na contagem. O deslocamento do pilar usa destino absoluto e não se acumula.
- GLB validado: 13 raízes de cadeira independentes, filhos, propriedades e poses preservadas com conversão Z-up → Y-up; textura de piso embutida.
- Scripts compilados com `compileall`.

### Arquivos entregues

- `modelos/labsea.blend`: modelo final atualizado.
- `saida/imagens_sinteticas/camera_1.png` a `camera_4.png` e `grid_cameras.png`.
- `saida/comparacoes/final_20261018/camera_1_comparison.png` a `camera_4_comparison.png`, diferenças e métricas atuais.
- `saida/labsea.glb`: versão para visualizadores glTF/Three.js.
- `scene_data/objects.json`, `desk_observations.json`, `floor_markers.json` e `landmarks.json`.
- `docs/inventario.csv`, `docs/validacao_resumo.json` e este relatório.

### Limites da revisão

As vistas 1 e 2 permitem conferir bancadas laterais, armários e mesa L; as vistas 3 e 4 mostram melhor as mesas sob as janelas e a GTMax. Restam diferenças de detalhes dos móveis, oclusões, reflexos e iluminação. A janela direita e o pilar precisam de levantamento para confirmar sua junção após a revisão provisória. As larguras das mesas foram confirmadas pelo usuário, mas profundidades, forro e várias posições ainda são estimativas. A reconstrução atual foi renderizada e comparada nas quatro perspectivas; **não constitui um levantamento métrico completo do laboratório**.
