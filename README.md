# RecuDaGa para Windows

Aplicación local de recuperación en español. Requiere **Windows y Python 3.10 o posterior** con Tkinter. No instala paquetes Python. Iníciala con **Iniciar RecuDaGa.cmd** o, desde esta carpeta, con el comando py -3 -m RecuDaGa.

## Uso

1. Conecta el disco de origen. Pulsa **Actualizar discos**.
2. Para carpetas o unidades que Windows abre, elige **Archivos accesibles** y selecciona la carpeta raíz.
3. Si la unidad no aparece en el Explorador pero sí figura como disco físico, elige **Disco no reconocido / análisis profundo** y el dispositivo físico mostrado. También se puede elegir una imagen de disco.
4. Selecciona una **carpeta ya existente en otro disco físico** como destino. La aplicación comprueba el número de disco de origen y destino y bloquea la operación si coinciden o no puede verificarlo.
5. Inicia el proceso. **Cancelar** detiene el recorrido o el motor externo; los archivos ya escritos permanecen en la carpeta del trabajo. Al terminar se crea **informe.json**.

La salida se guarda bajo una carpeta RecuDaGa_FECHA_HORA en el destino. En el modo de archivos accesibles mantiene nombres y carpetas. El informe indica validado, no_verificado, dañado, parcial, fallido o reparado_parcialmente, con la evidencia de cada caso.

## Funciones y límites exactos

| Función | Estado |
| --- | --- |
| Copiar archivos legibles de cualquier extensión | Implementado; errores de lectura producen un resultado parcial o fallido. |
| Analizar un disco físico sin letra | Implementado si Windows permite enumerarlo y leerlo; puede requerir administrador. Si el dispositivo no aparece en Windows, no es recuperable por esta aplicación. |
| Extraer por firmas sin dependencias | Implementado para JPEG, PNG y PDF, con límite de 128 MiB por candidato. Un fragmento sin marcador final se guarda como parcial. No conserva nombres o rutas originales. JPEG y PDF quedan no_verificado si solo se comprueban sus marcadores. |
| Recuperación profunda con PhotoRec | Integración opcional; busca los formatos admitidos por la versión de PhotoRec elegida. No se incluye PhotoRec en el paquete. No se ha probado con un disco real en este entorno. |
| PNG | Se comprueban bloques y CRC; no se repara. |
| ZIP, DOCX, XLSX, PPTX, ODT, ODS, ODP, EPUB, JAR | Se comprueban entradas y CRC. Si una entrada está dañada y hay otras sanas, se crea una nueva copia sin la entrada dañada; el informe la llama reparado_parcialmente. La validez semántica de documentos Office no se comprueba. |
| TAR, GZ, BZ2, XZ | Se leen o descomprimen para detectar errores; no se reparan. |
| WAV | Se comprueban cabecera y longitud declarada de los datos; no se repara. |
| JPEG, PDF, GIF | Solo se comprueban marcadores; no se afirma validación completa ni reparación. |
| MP3, MP4, MKV, AVI, MOV, FLAC, 7Z, RAR, DOC, XLS, PPT y otros | Se pueden copiar; no se validan ni reparan internamente. PhotoRec puede encontrar algunos de ellos según su versión y sus firmas. |

El análisis por firmas puede producir falsos positivos y no reconstruye archivos fragmentados. Ningún método puede recrear datos que ya no existen. Los resultados recuperados deben abrirse y revisarse antes de sustituir cualquier original.

## PhotoRec

Descarga TestDisk/PhotoRec únicamente desde [CGSecurity](https://www.cgsecurity.org/wiki/PhotoRec). Selecciona photorec_win.exe con el botón de la aplicación. PhotoRec se distribuye bajo [GPL v2 o posterior](https://www.cgsecurity.org/wiki/PhotoRec). RecuDaGa solo ejecuta el programa que selecciones; no redistribuye su binario. Su [sintaxis de automatización](https://www.cgsecurity.org/wiki/Scripted_run) se usa para buscar en todo el espacio y guardar los hallazgos en el disco de destino.

## Comprobaciones realizadas

Se ejecutaron pruebas con archivos creados para la ocasión: copia preservando rutas, PNG válido y truncado, reconstrucción de ZIP con una entrada corrupta, imagen pequeña con PNG incrustado, fragmento incompleto, cancelación, lectura fallida simulada, bloqueo de destino en el mismo disco y construcción del comando PhotoRec con proceso simulado. Se verificó que la interfaz abre. No se probó una recuperación real ni el binario PhotoRec porque esta sesión no dispone de un disco de pruebas ni del ejecutable PhotoRec.

Pruebas: py -3 -m unittest discover -s RecuDaGa/tests -t . -v desde la carpeta del paquete.

