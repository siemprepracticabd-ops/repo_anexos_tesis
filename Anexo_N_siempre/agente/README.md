# agente del reloj

lee las marcaciones del reloj steren clk-960 por red (protocolo zk, puerto 4370) y las envia por lotes a la api.

uso rapido:

```bash
python -m pip install -r requirements.txt
copy config.example.json config.json
python importer.py --config config.json
```

notas:

- valida que el numero de serie del reloj coincida con `lector_serie` antes de enviar.
- las horas del reloj son locales y se envian con zona horaria (`utc_offset_horas`).
- la cola sqlite (`queue.sqlite3`) evita perder o duplicar marcaciones si no hay internet.
- si el reloj cambia de ip, el agente lo busca en la red de la pc y guarda la nueva ip en `config.json`.
- `config.json` lleva la clave del reloj: no se sube a git.
