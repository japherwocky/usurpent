# USURPENT

A multiplayer snake-like MMO game built with Python/Tornado backend and JavaScript/D3.js frontend.

## Overview

USURPENT is a real-time multiplayer game where players control entities that move through a shared game space. The project demonstrates client-server game architecture with smooth animations and particle effects using D3.js for visualization.

## Features

- **Real-time multiplayer gameplay** - Multiple players can join and interact in the same game space
- **Smooth animations** - Uses D3.js for fluid entity movement and particle effects
- **Mouse-controlled movement** - Entities follow mouse cursor with physics-based movement
- **Particle system** - Dynamic particle effects with color shifting and rotation
- **Responsive design** - Scales to different screen sizes
- **Web-based** - Runs entirely in the browser with no additional client software

## Technology Stack

### Backend
- **Python 3** - Core language
- **Tornado** - Async web framework for real-time applications
- **Markdown** - For documentation rendering

### Frontend
- **JavaScript (ES6+)** - Game logic and client-side functionality
- **D3.js v7** - Data visualization and animations
- **HTML5/CSS3** - Structure and styling
- **SVG** - Game rendering

## Project Structure

```
usurpent/
├── usurpent.py          # Main Tornado application server
├── requirements.txt     # Python dependencies
├── Makefile            # Build and development commands
├── static/
│   ├── game.js         # Frontend game logic
│   └── netcodedemo.html # Network demo implementation
├── templates/
│   └── index.html      # Main game interface
└── README.md           # This file
```

## Installation & Setup

### Prerequisites
- Python 3.6+
- pip (Python package manager)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd usurpent
   ```

2. **Set up the development environment**
   ```bash
   make init
   ```
   This creates a virtual environment and installs dependencies.

3. **Run the development server**
   ```bash
   make dev
   ```
   The server will start on `http://localhost:8001` with debug mode enabled.

4. **Run in production mode**
   ```bash
   make demo
   ```

### Manual Setup

If you prefer not to use the Makefile:

1. Create virtual environment:
   ```bash
   python3 -m venv ./env
   source ./env/bin/activate  # On Windows: .\env\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the server:
   ```bash
   python usurpent.py --port=8001 --debug
   ```

## Usage

1. Start the server as described above
2. Open your browser and navigate to `http://localhost:8001`
3. Enter your player name and click "PLAY"
4. Move your mouse to control your entity
5. Watch as particles swirl around and your entity follows the cursor

## Game Mechanics

- **Entity Movement**: Your entity (colored circle) follows your mouse cursor with physics-based acceleration
- **Particle System**: Background particles rotate and shift colors continuously
- **Real-time Updates**: The game updates at ~30 FPS for smooth gameplay
- **Coordinate System**: Uses a mathematical coordinate system with D3.js scaling

## Development

### Available Commands

- `make init` - Set up development environment
- `make dev` - Run development server with debug mode
- `make demo` - Run production server
- `make test` - Run test suite
- `make clean` - Remove virtual environment

### Configuration

The server can be configured with command-line options:

- `--port=PORT` - Set server port (default: 8001)
- `--debug` - Enable debug mode for development
- `--runtests` - Run the test suite

### Code Structure

- **usurpent.py**: Main Tornado application with URL routing and request handlers
- **static/game.js**: Complete game implementation including:
  - Entity management and physics
  - Particle system
  - Mouse interaction handling
  - D3.js visualization setup
- **templates/index.html**: Game interface with login screen and SVG canvas

## Network Architecture

The project includes a network demo (`static/netcodedemo.html`) that demonstrates:
- Client-server communication patterns
- Lag simulation and compensation
- Entity interpolation
- Client-side prediction and server reconciliation

This demo is based on Gabriel Gambetta's fast-paced multiplayer series and provides insights into real-time networking challenges.

## Contributing

This project appears to be abandoned but welcomes contributions. Areas for improvement:

1. **Multiplayer functionality** - Currently single-player only
2. **Collision detection** - Add entity interactions
3. **Score system** - Track player progress
4. **Game modes** - Different gameplay variations
5. **Performance optimization** - Improve rendering efficiency
6. **Mobile support** - Touch controls for mobile devices

## License

No explicit license is provided. Please contact the original author for usage permissions.

## Author

Originally created by Japherwocky. The project appears to be abandoned but serves as an excellent example of real-time web game development.