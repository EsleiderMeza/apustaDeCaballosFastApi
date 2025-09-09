# API de Apuestas de Caballos

Esta es una api creado con  FastAPI y SQLite.  
que permite crear apuestas, simular resultados y consultar estadísticas de los caballos.

## Cómo ejecutar

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Ejecutar el servidor:
```bash
uvicorn horse_betting_main:app --reload
```

3. Abrir en el navegador:
- API base → http://localhost:8000  
- Documentación interactiva (Swagger UI) → http://localhost:8000/docs  

## Decisiones de diseño

1. **SQLite con queries directas**  
   Se usa SQLite porque es ligero y no necesita configuración extra. Se prefieren queries SQL directas en vez de un ORM para mantenerlo simple y fácil de entender.

2. **Cálculo de odds**  
   Las odds (cuotas) se calculan con el historial del caballo: `victorias / carreras`.  
   - Si nunca ha corrido, se asigna probabilidad 0.1 por defecto.  
   - Cuanto mejor el historial, menores las odds (más favorito).  

3. **Ganador simulado con probabilidades**  
   El ganador se elige al azar, pero usando la probabilidad histórica de cada caballo como peso. Así los favoritos tienen más chance, aunque no siempre ganan.

## Endpoints principales

### Carreras
- `GET /races/next` → Ver la próxima carrera programada y sus caballos con odds.  
- `POST /races/{race_id}/result` → Simular el resultado de la carrera y liquidar apuestas.  
- `GET /races/{race_id}/results` → Consultar los ganadores de una carrera terminada.  

### Apuestas
- `POST /bets` → Crear una apuesta (solo si la carrera sigue en estado *scheduled*).  

### Caballos
- `GET /horses/{horse_id}/stats` → Ver estadísticas de un caballo (carreras corridas, ganadas, probabilidad de victoria, odds sugeridas).  

## Ejemplos con curl

### 1. Ver próxima carrera
```bash
curl http://localhost:8000/races/next
```

### 2. Hacer una apuesta
```bash
curl -X POST http://localhost:8000/bets \
  -H "Content-Type: application/json" \
  -d '{
    "user": "juan@test.com",
    "raceId": "r1", 
    "horseId": "h1",
    "amount": 1000
  }'
```

### 3. Publicar resultado de la carrera
```bash
curl -X POST http://localhost:8000/races/r1/result | jq
```

### 4. Consultar ganadores
```bash
curl http://localhost:8000/races/r1/results | jq
```

## Base de datos

La app usa SQLite (archivo `horses.db`).  
Las tablas se crean automáticamente al iniciar:

- `horses` → Caballos (id, nombre, carreras corridas, carreras ganadas).  
- `races` → Carreras (id, nombre, fecha/hora, estado, caballo ganador).  
- `race_entries` → Relación carrera ↔ caballos + odds.  
- `bets` → Apuestas de los usuarios (congelan odds al momento de apostar).  

Al arrancar la app por primera vez se insertan datos de prueba automáticamente (una carrera con cuatro caballos).
