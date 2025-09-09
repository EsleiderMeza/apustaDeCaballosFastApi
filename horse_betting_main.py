from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import json
from datetime import datetime, timedelta
import random
import uuid

# Inicializar FastAPI
app = FastAPI()

# Configuración de la base de datos
DATABASE = "horses.db"

# Modelos Pydantic básicos
class BetRequest(BaseModel):
    user: str
    raceId: str
    horseId: str
    amount: int

class BetResponse(BaseModel):
    betId: str
    user: str
    raceId: str
    horseId: str
    amount: int
    odds: float
    status: str
    createdAt: str

# Función para inicializar la base de datos
def init_db():
    conetc= sqlite3.connect(DATABASE)
    cursor =  conetc.cursor()
    
    # Crear tablas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS horses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            races_run INTEGER DEFAULT 0,
            races_won INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS races (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            start_time TEXT NOT NULL,
            status TEXT DEFAULT 'scheduled',
            winning_horse_id TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_entries (
            id TEXT PRIMARY KEY,
            race_id TEXT,
            horse_id TEXT,
            odds REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bets (
            id TEXT PRIMARY KEY,
            user TEXT NOT NULL,
            race_id TEXT,
            horse_id TEXT,
            amount INTEGER,
            odds REAL,
            status TEXT DEFAULT 'pending',
            payout INTEGER DEFAULT 0,
            created_at TEXT
        )
    ''')
    
    conetc.commit()
    conetc.close()

# Función para sembrar datos de prueba
def seed_data():
    conne = sqlite3.connect(DATABASE)
    cursor = conne.cursor()
    
    # Verificar si ya hay datos
    cursor.execute("SELECT COUNT(*) FROM horses")
    if cursor.fetchone()[0] > 0:
        conne.close()
        return
    
    # Insertar caballos
    horses = [
        ("h1", "Relámpago", 10, 2),
        ("h2", "Trueno", 8, 2), 
        ("h3", "Viento", 12, 5),
        ("h4", "Sombra", 15, 1)
    ]
    
    for horse in horses:
        cursor.execute("INSERT INTO horses VALUES (?, ?, ?, ?)", horse)
    
    # Insertar carrera de prueba
    future_time = (datetime.now() + timedelta(hours=1)).isoformat()
    cursor.execute("INSERT INTO races VALUES (?, ?, ?, ?, ?)", 
                   ("r1", "Clásico Shelby", future_time, "scheduled", None))
    
    # Insertar inscripciones con odds calculadas
    entries = [
        ("e1", "r1", "h1", 5.0),  # odds calculadas manualmente
        ("e2", "r1", "h2", 4.0),
        ("e3", "r1", "h3", 2.4),
        ("e4", "r1", "h4", 15.0)
    ]
    
    for entry in entries:
        cursor.execute("INSERT INTO race_entries VALUES (?, ?, ?, ?)", entry)
    
    conne.commit()
    conne.close()
    print("Datos de prueba insertados")

# Función para calcular probabilidad de un caballo
def get_horse_probability(races_run, races_won):
    if races_run == 0:
        return 0.1  # Probabilidad por defecto si no ha corrido nunca 
    return races_won / races_run

# Función para calcular odds a partir de probabilidad
def calculate_odds(probability):
    return 1 / probability

# Endpoints

@app.get("/races/next")
def get_next_race():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Buscar próxima carrera programada
    cursor.execute("""
        SELECT id, name, start_time, status 
        FROM races 
        WHERE status = 'scheduled' 
        ORDER BY start_time ASC 
        LIMIT 1
    """)
    
    race = cursor.fetchone()
    if not race:
        conn.close()
        raise HTTPException(status_code=404, detail={
            "error": "NoNextRace", 
            "message": "No hay carreras programadas"
        })
    
    race_id = race[0]
    
    # Obtener caballos inscritos
    cursor.execute("""
        SELECT re.horse_id, h.name, re.odds
        FROM race_entries re
        JOIN horses h ON re.horse_id = h.id
        WHERE re.race_id = ?
    """, (race_id,))
    
    horses = cursor.fetchall()
    conn.close()
    
    entries = []
    for horse in horses:
        entries.append({
            "horseId": horse[0],
            "name": horse[1], 
            "odds": horse[2]
        })
    
    return {
        "raceId": race[0],
        "name": race[1],
        "startTime": race[2], 
        "status": race[3],
        "entries": entries
    }

@app.post("/bets", status_code=201)
def create_bet(bet: BetRequest):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Verificar que la carrera existe
    cursor.execute("SELECT start_time, status FROM races WHERE id = ?", (bet.raceId,))
    race = cursor.fetchone()
    
    if not race:
        conn.close()
        raise HTTPException(status_code=404, detail={
            "error": "RaceNotFound",
            "message": "La carrera no existe"
        })
    
    # Verificar estado y tiempo
    if race[1] != "scheduled":
        conn.close()
        raise HTTPException(status_code=400, detail={
            "error": "RaceNotScheduled", 
            "message": "La carrera no está programada"
        })
    
    race_time = datetime.fromisoformat(race[0])
    if datetime.now() >= race_time:
        conn.close()
        raise HTTPException(status_code=400, detail={
            "error": "BettingClosed",
            "message": "Las apuestas están cerradas"
        })
    
    # Verificar que el caballo está en la carrera y obtener odds
    cursor.execute("""
        SELECT odds FROM race_entries 
        WHERE race_id = ? AND horse_id = ?
    """, (bet.raceId, bet.horseId))
    
    entry = cursor.fetchone()
    if not entry:
        conn.close()
        raise HTTPException(status_code=404, detail={
            "error": "HorseNotInRace",
            "message": "El caballo no está inscrito"
        })
    
    # Crear apuesta
    bet_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT INTO bets (id, user, race_id, horse_id, amount, odds, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (bet_id, bet.user, bet.raceId, bet.horseId, bet.amount, entry[0], created_at))
    
    conn.commit()
    conn.close()
    
    return {
        "betId": bet_id,
        "user": bet.user,
        "raceId": bet.raceId, 
        "horseId": bet.horseId,
        "amount": bet.amount,
        "odds": entry[0],
        "status": "pending",
        "createdAt": created_at
    }

@app.get("/")
def root():
    return {
        "message": "Bienvenido a la API de apuestas de caballos ",
        "endpoints": ["/races/next", "/bets", "/races/{id}/result", "/races/{id}/results", "/horses/{id}/stats"],
        "docs": "Visita /docs para probar la API con Swagger UI"
    }

@app.post("/races/{race_id}/result")
def publish_result(race_id: str):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Verificar que la carrera existe y está programada
    cursor.execute("SELECT status FROM races WHERE id = ?", (race_id,))
    race = cursor.fetchone()
    
    if not race:
        conn.close()
        raise HTTPException(status_code=404, detail={
            "error": "RaceNotFound",
            "message": "La carrera no existe"
        })
    
    if race[0] != "scheduled":
        conn.close()
        raise HTTPException(status_code=400, detail={
            "error": "RaceAlreadyFinished", 
            "message": "La carrera ya terminó"
        })
    
    # Obtener caballos y calcular probabilidades
    cursor.execute("""
        SELECT h.id, h.races_run, h.races_won
        FROM race_entries re
        JOIN horses h ON re.horse_id = h.id  
        WHERE re.race_id = ?
    """, (race_id,))
    
    horses = cursor.fetchall()
    
    # Simular ganador con probabilidades
    horse_probs = []
    for horse in horses:
        prob = get_horse_probability(horse[1], horse[2])
        horse_probs.append((horse[0], prob))
    
    # Sorteo ponderado simple
    total_prob = sum(p[1] for p in horse_probs)
    rand_val = random.random() * total_prob
    
    cumulative = 0
    winner_id = horse_probs[0][0]  # fallback
    
    for horse_id, prob in horse_probs:
        cumulative += prob
        if rand_val <= cumulative:
            winner_id = horse_id
            break
    
    # Actualizar estadísticas de caballos
    for horse in horses:
        horse_id = horse[0]
        new_races_run = horse[1] + 1
        new_races_won = horse[2] + (1 if horse_id == winner_id else 0)
        
        cursor.execute("""
            UPDATE horses 
            SET races_run = ?, races_won = ? 
            WHERE id = ?
        """, (new_races_run, new_races_won, horse_id))
    
    # Actualizar carrera
    cursor.execute("""
        UPDATE races 
        SET status = 'finished', winning_horse_id = ? 
        WHERE id = ?
    """, (winner_id, race_id))
    
    # Liquidar apuestas
    cursor.execute("SELECT * FROM bets WHERE race_id = ?", (race_id,))
    bets = cursor.fetchall()
    
    payouts = []
    for bet in bets:
        bet_id = bet[0]
        user = bet[1] 
        horse_id = bet[3]
        amount = bet[4]
        odds = bet[5]
        
        if horse_id == winner_id:
            status = "won"
            payout = int(amount * odds)
        else:
            status = "lost"
            payout = 0
        
        cursor.execute("""
            UPDATE bets 
            SET status = ?, payout = ? 
            WHERE id = ?
        """, (status, payout, bet_id))
        
        payouts.append({
            "betId": bet_id,
            "user": user,
            "status": status,
            "payout": payout
        })
    
    conn.commit()
    conn.close()
    
    return {
        "raceId": race_id,
        "status": "finished",
        "winningHorseId": winner_id,
        "payouts": payouts
    }

@app.get("/races/{race_id}/results")
def get_race_results(race_id: str):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Obtener info de la carrera
    cursor.execute("SELECT status, winning_horse_id FROM races WHERE id = ?", (race_id,))
    race = cursor.fetchone()
    
    if not race:
        conn.close()
        raise HTTPException(status_code=404, detail={
            "error": "RaceNotFound",
            "message": "La carrera no existe"
        })
    
    # Obtener apuestas ganadoras
    cursor.execute("""
        SELECT id, user, amount, odds, payout
        FROM bets 
        WHERE race_id = ? AND status = 'won'
    """, (race_id,))
    
    winning_bets = cursor.fetchall()
    conn.close()
    
    winners = []
    for bet in winning_bets:
        winners.append({
            "betId": bet[0],
            "user": bet[1],
            "amount": bet[2],
            "oddsAtBet": bet[3], 
            "payout": bet[4]
        })
    
    return {
        "raceId": race_id,
        "status": race[0],
        "winningHorseId": race[1],
        "winners": winners
    }

@app.get("/horses/{horse_id}/stats")
def get_horse_stats(horse_id: str):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM horses WHERE id = ?", (horse_id,))
    horse = cursor.fetchone()
    
    if not horse:
        conn.close()
        raise HTTPException(status_code=404, detail={
            "error": "HorseNotFound", 
            "message": "El caballo no existe"
        })
    
    conn.close()
    
    win_prob = get_horse_probability(horse[2], horse[3])
    suggested_odds = calculate_odds(win_prob)
    
    return {
        "horseId": horse[0],
        "name": horse[1],
        "racesRun": horse[2],
        "racesWon": horse[3], 
        "winProbability": win_prob,
        "suggestedOdds": suggested_odds
    }

# Inicializar todo al arrancar
@app.on_event("startup")
def startup_event():
    init_db()
    seed_data()

# Para ejecutar: uvicorn app:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)