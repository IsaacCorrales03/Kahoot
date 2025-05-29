from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string
import time
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu-clave-secreta-aqui'
socketio = SocketIO(app, cors_allowed_origins="*")

# Almacenar las salas activas
rooms = {}
# Almacenar preguntas y respuestas
questions_pool = [
    {
        "question": "What is the full name of the Statue of Liberty?",
        "options": ["Liberty Enlightening the World", "The Lady of Liberty", "The Statue of Independence", "America's Torch"],
        "correct": 0
    },
    {
        "question": "In what year was the Empire State Building inaugurated?",
        "options": ["1929", "1931", "1933", "1935"],
        "correct": 1
    },
    {
        "question": "How many main parks does Central Park have?",
        "options": ["1", "2", "3", "4"],
        "correct": 0
    },
    {
        "question": "What does 'Manhattan' mean in the Native American language?",
        "options": ["Rocky island", "Sacred land", "Freshwater", "Island of hills"],
        "correct": 0
    },
    {
        "question": "What is the most famous bridge in New York?",
        "options": ["Manhattan Bridge", "Brooklyn Bridge", "Williamsburg Bridge", "Queensboro Bridge"],
        "correct": 1
    },
    {
        "question": "In which borough is Times Square located?",
        "options": ["Brooklyn", "Queens", "Manhattan", "Bronx"],
        "correct": 2
    },
    {
        "question": "Approximately how many subway lines does NYC have?",
        "options": ["15", "20", "25", "30"],
        "correct": 2
    },
    {
        "question": "Which famous park is located in the Bronx?",
        "options": ["Prospect Park", "Central Park", "Bryant Park", "Bronx Zoo (Bronx Park)"],
        "correct": 3
    },
    {
        "question": "What is currently the tallest building in NYC?",
        "options": ["Empire State", "One World Trade Center", "Central Park Tower", "432 Park Avenue"],
        "correct": 2
    },
    {
        "question": "On which island is the Statue of Liberty located?",
        "options": ["Manhattan", "Staten Island", "Liberty Island", "Ellis Island"],
        "correct": 2
    },
    {
        "question": "What is New York's most famous nickname?",
        "options": ["The Big Apple", "The Golden City", "The Metropolis", "The Imperial City"],
        "correct": 0
    },
    {
        "question": "Which theater is famous on Broadway?",
        "options": ["Apollo Theater", "Madison Square Garden", "Lincoln Center", "Majestic Theatre"],
        "correct": 3
    },
    {
        "question": "How many floors does the Empire State Building have?",
        "options": ["100", "102", "105", "110"],
        "correct": 1
    },
    {
        "question": "Which river separates Manhattan from the Bronx?",
        "options": ["Hudson River", "East River", "Harlem River", "Jamaica River"],
        "correct": 2
    },
    {
        "question": "In what year did 9/11 occur?",
        "options": ["2000", "2001", "2002", "2003"],
        "correct": 1
    },
    {
        "question": "What is the longest street in Manhattan?",
        "options": ["5th Avenue", "Broadway", "Madison Avenue", "Park Avenue"],
        "correct": 1
    },
    {
        "question": "Which famous university is in NYC?",
        "options": ["Harvard", "Yale", "Columbia", "Princeton"],
        "correct": 2
    },
    {
        "question": "What is the largest Chinatown outside of Asia?",
        "options": ["Chinatown SF", "Chinatown NYC", "Chinatown LA", "Chinatown Toronto"],
        "correct": 1
    },
    {
        "question": "Which museum is in Central Park?",
        "options": ["MoMA", "Guggenheim", "Metropolitan Museum", "Whitney"],
        "correct": 2
    },
    {
        "question": "When was the first skyscraper in NYC built?",
        "options": ["1885", "1890", "1895", "1900"],
        "correct": 0
    }
]

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/host')
def host():
    return render_template('host.html')

@app.route('/join')
def join():
    return render_template('join.html')

@app.route('/create_room', methods=['POST'])
def create_room():
    room_code = generate_room_code()
    while room_code in rooms:
        room_code = generate_room_code()
    
    # Seleccionar 10 preguntas aleatorias
    selected_questions = random.sample(questions_pool, 10)
    
    rooms[room_code] = {
        'host': None,
        'players': {},
        'questions': selected_questions,
        'current_question': 0,
        'game_state': 'waiting',  # waiting, question, results, finished
        'question_start_time': None,
        'answers_received': {}
    }
    
    return jsonify({'room_code': room_code})

@socketio.on('host_join')
def handle_host_join(data):
    room_code = data['room_code']
    if room_code in rooms:
        rooms[room_code]['host'] = request.sid
        join_room(room_code)
        emit('host_joined', {'success': True})
        # Enviar lista actual de jugadores
        emit('players_update', {'players': list(rooms[room_code]['players'].values())})
    else:
        emit('host_joined', {'success': False, 'error': 'Sala no encontrada'})

@socketio.on('player_join')
def handle_player_join(data):
    room_code = data['room_code']
    player_name = data['player_name']
    
    if room_code not in rooms:
        emit('join_result', {'success': False, 'error': 'Sala no encontrada'})
        return
    
    if rooms[room_code]['game_state'] != 'waiting':
        emit('join_result', {'success': False, 'error': 'El juego ya comenzó'})
        return
    
    # Agregar jugador
    rooms[room_code]['players'][request.sid] = {
        'name': player_name,
        'score': 0,
        'sid': request.sid
    }
    
    join_room(room_code)
    emit('join_result', {'success': True})
    
    # Notificar al host sobre el nuevo jugador
    socketio.emit('players_update', 
                 {'players': list(rooms[room_code]['players'].values())}, 
                 room=room_code)

@socketio.on('start_game')
def handle_start_game(data):
    room_code = data['room_code']
    if room_code in rooms and rooms[room_code]['host'] == request.sid:
        rooms[room_code]['game_state'] = 'question'
        rooms[room_code]['current_question'] = 0
        show_next_question(room_code)

def show_next_question(room_code):
    room = rooms[room_code]
    if room['current_question'] < len(room['questions']):
        question_data = room['questions'][room['current_question']]
        room['question_start_time'] = time.time()
        room['answers_received'] = {}
        
        # Enviar pregunta completa al host
        socketio.emit('new_question', {
            'question': question_data['question'],
            'options': question_data['options'],
            'question_number': room['current_question'] + 1,
            'total_questions': len(room['questions'])
        }, room=rooms[room_code]['host'])
        
        # Enviar solo opciones a los jugadores
        for player_sid in room['players']:
            socketio.emit('new_question_player', {
                'options': ['A', 'B', 'C', 'D'],
                'question_number': room['current_question'] + 1,
                'total_questions': len(room['questions'])
            }, room=player_sid)
    else:
        # Juego terminado
        room['game_state'] = 'finished'
        final_rankings = sorted(room['players'].values(), key=lambda x: x['score'], reverse=True)
        socketio.emit('game_finished', {'rankings': final_rankings}, room=room_code)

@socketio.on('player_answer')
def handle_player_answer(data):
    room_code = data['room_code']
    answer = data['answer']  # 0, 1, 2, 3
    
    if room_code not in rooms:
        return
    
    room = rooms[room_code]
    player_sid = request.sid
    
    if player_sid not in room['players']:
        return
    
    if player_sid in room['answers_received']:
        return  # Ya respondió
    
    # Registrar respuesta y tiempo
    current_time = time.time()
    response_time = current_time - room['question_start_time']
    
    room['answers_received'][player_sid] = {
        'answer': answer,
        'time': response_time
    }
    
    # Verificar si la respuesta es correcta
    correct_answer = room['questions'][room['current_question']]['correct']
    if answer == correct_answer:
        # Calcular puntos basado en velocidad de respuesta
        position = len([r for r in room['answers_received'].values() if r.get('answer') == correct_answer])
        points = max(1, 11 - position)  # 10 puntos al primero, 9 al segundo, etc.
        room['players'][player_sid]['score'] += points
    
    # Notificar al host sobre la respuesta
    socketio.emit('answer_received', {
        'player': room['players'][player_sid]['name'],
        'answer': chr(65 + answer),  # Convertir 0,1,2,3 a A,B,C,D
        'correct': answer == correct_answer,
        'total_answers': len(room['answers_received'])
    }, room=room['host'])

@socketio.on('next_question')
def handle_next_question(data):
    room_code = data['room_code']
    if room_code in rooms and rooms[room_code]['host'] == request.sid:
        # Mostrar resultados de la pregunta actual
        room = rooms[room_code]
        correct_answer = room['questions'][room['current_question']]['correct']
        
        # Enviar resultados
        socketio.emit('question_results', {
            'correct_answer': chr(65 + correct_answer),
            'question': room['questions'][room['current_question']]['question'],
            'rankings': sorted(room['players'].values(), key=lambda x: x['score'], reverse=True)
        }, room=room_code)
        
        # Esperar un poco y continuar con la siguiente pregunta
        room['current_question'] += 1
        socketio.sleep(3)
        show_next_question(room_code)

@socketio.on('disconnect')
def handle_disconnect():
    # Remover jugador de todas las salas
    for room_code in list(rooms.keys()):
        room = rooms[room_code]
        if request.sid in room['players']:
            del room['players'][request.sid]
            socketio.emit('players_update', 
                         {'players': list(room['players'].values())}, 
                         room=room_code)
        
        if room['host'] == request.sid:
            # Si el host se desconecta, cerrar la sala
            socketio.emit('host_disconnected', room=room_code)
            del rooms[room_code]

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)