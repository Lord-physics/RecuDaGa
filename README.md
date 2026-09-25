# RecuDaGa para Windows

Aplicaci�n local de recuperaci�n en espa�ol. Requiere **Windows y Python 3.10 o posterior** con Tkinter. No instala paquetes Python. In�ciala con **Iniciar RecuDaGa.cmd** o, desde esta carpeta, con el comando py -3 -m RecuDaGa.

## Uso

1. Conecta el disco de origen. Pulsa **Actualizar discos**.
2. Para carpetas o unidades que Windows abre, elige **Archivos accesibles** y selecciona la carpeta ra�z.
3. Si la unidad no aparece en el Explorador pero s� figura como disco f�sico, elige **Disco no reconocido / an�lisis profundo** y el dispositivo f�sico mostrado. Tambi�n se puede elegir una imagen de disco.
4. Selecciona una **carpeta ya existente en otro disco f�sico** como destino. La aplicaci�n comprueba el n�mero de disco de origen y destino y bloquea la operaci�n si coinciden o no puede verificarlo.
5. Inicia el proceso. **Cancelar** detiene el recorrido o el motor externo; los archivos ya escritos permanecen en la carpeta del trabajo. Al terminar se crea **informe.json**.

La salida se guarda bajo una carpeta RecuDaGa_FECHA_HORA en el destino. En el modo de archivos accesibles mantiene nombres y carpetas. El informe indica validado, no_verificado, da�ado, parcial, fallido o reparado_parcialmente, con la evidencia de cada caso.

## Funciones y l�mites exactos

| Funci�n | Estado |
| --- | --- |
| Copiar archivos legibles de cualquier extensi�n | Implementado; errores de lectura producen un resultado parcial o fallido. |
| Analizar un disco f�sico sin letra | Implementado si Windows permite enumerarlo y leerlo; puede requerir administrador. Si el dispositivo no aparece en Windows, no es recuperable por esta aplicaci�n. |
| Extraer por firmas sin dependencias | Implementado para JPEG, PNG y PDF, con l�mite de 128 MiB por candidato. Un fragmento sin marcador final se guarda como parcial. No conserva nombres o rutas originales. JPEG y PDF quedan no_verificado si solo se comprueban sus marcadores. |
| Recuperaci�n profunda con PhotoRec | Integraci�n opcional; busca los formatos admitidos por la versi�n de PhotoRec elegida. No se incluye PhotoRec en el paquete. No se ha probado con un disco real en este entorno. |
| PNG | Se comprueban bloques y CRC; no se repara. |
| ZIP, DOCX, XLSX, PPTX, ODT, ODS, ODP, EPUB, JAR | Se comprueban entradas y CRC. Si una entrada est� da�ada y hay otras sanas, se crea una nueva copia sin la entrada da�ada; el informe la llama reparado_parcialmente. La validez sem�ntica de documentos Office no se comprueba. |
| TAR, GZ, BZ2, XZ | Se leen o descomprimen para detectar errores; no se reparan. |
| WAV | Se comprueban cabecera y longitud declarada de los datos; no se repara. |
| JPEG, PDF, GIF | Solo se comprueban marcadores; no se afirma validaci�n completa ni reparaci�n. |
| MP3, MP4, MKV, AVI, MOV, FLAC, 7Z, RAR, DOC, XLS, PPT y otros | Se pueden copiar; no se validan ni reparan internamente. PhotoRec puede encontrar algunos de ellos seg�n su versi�n y sus firmas. |

El an�lisis por firmas puede producir falsos positivos y no reconstruye archivos fragmentados. Ning�n m�todo puede recrear datos que ya no existen. Los resultados recuperados deben abrirse y revisarse antes de sustituir cualquier original.

## PhotoRec

Descarga TestDisk/PhotoRec �nicamente desde [CGSecurity](https://www.cgsecurity.org/wiki/PhotoRec). Selecciona photorec_win.exe con el bot�n de la aplicaci�n. PhotoRec se distribuye bajo [GPL v2 o posterior](https://www.cgsecurity.org/wiki/PhotoRec). RecuDaGa solo ejecuta el programa que selecciones; no redistribuye su binario. Su [sintaxis de automatizaci�n](https://www.cgsecurity.org/wiki/Scripted_run) se usa para buscar en todo el espacio y guardar los hallazgos en el disco de destino.

## Comprobaciones realizadas

Se ejecutaron pruebas con archivos creados para la ocasi�n: copia preservando rutas, PNG v�lido y truncado, reconstrucci�n de ZIP con una entrada corrupta, imagen peque�a con PNG incrustado, fragmento incompleto, cancelaci�n, lectura fallida simulada, bloqueo de destino en el mismo disco y construcci�n del comando PhotoRec con proceso simulado. Se verific� que la interfaz abre. No se prob� una recuperaci�n real ni el binario PhotoRec porque esta sesi�n no dispone de un disco de pruebas ni del ejecutable PhotoRec.

Pruebas: py -3 -m unittest discover -s RecuDaGa/tests -t . -v desde la carpeta del paquete.
