# Archivo histórico v2 del escritor 7f05898

Caso sintético generado el 2026-11-19 con `7f0589853ae854bc0bf6678ba30bd2e9f8f2591f`, extraído mediante `git archive` a un directorio temporal sin cambiar el checkout. El escritor produjo A v1, B v1 de seguimiento y C v2 guiado. El mismo código leyó C antes de empaquetarlo.

- ZIP: `chained-v1-7f05898.zip`, 10,628 bytes; SHA-256 `9e0ae5c409e866ddc40879b4897117eb9b7330348036b1ea46945b2ab6f4530e`.
- `review.json` C: SHA-256 `cd5efadcbfc7b0bb9680009d270741b804bae582dc947e5f1e522bfda967fa6e`.
- C omite `history_incomplete` y enlaza B v1, que a su vez enlaza A.

`tests/legacy_v2_fixture.py` conserva todos los bytes de resultado, informe y evidencia. Al copiar el fixture adapta únicamente la envoltura de ubicación del archivo nativo (`archive_root`, `run_dir` y el hash del manifiesto en ownership), porque estas rutas absolutas son propias de cada host. Comprueba después todos los hashes originales del payload. Las pruebas verifican inmutabilidad de la copia durante lectura y uso como antecedente, y rechazo de una evidencia alterada.

Sobre la misma copia reubicada, el lector original `7f05898` aprobó y el lector `94746a9` falló con `history_incomplete must preserve unknown historical observation hashes`. El lector ajustado acepta ese payload y permite un seguimiento v3 sin reescribirlo.

Para regenerar desde un repositorio que conserve el commit: `python -B -X utf8 tests/fixtures/pr37_legacy_v2/generate.py`. El script ejecuta el escritor antiguo en aislamiento y muestra los hashes resultantes. Sus UUID y fecha se generan normalmente: tras regenerarlo, actualiza el digest del fixture en el helper y los datos anteriores. Las pruebas ordinarias consumen el fixture sin requerir Git ni código histórico instalado.
