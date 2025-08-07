# D&D Telegram Bot

This is a Telegram bot designed to manage Dungeons & Dragons 5e adventures using the Grok API as a virtual Dungeon Master. It supports character creation, adventure management, combat scenarios, and interaction with the Grok API for narrative elements.

## Features

1. **Database Integration**: All game data, including characters, adventures, and items, are stored in a MariaDB database.

2. **Character Generation**: Players can generate characters with randomized stats and choose from different races, origins, and classes.

3. **Grok-Powered Adventures**: The Grok API generates adventure introductions and progresses the storyline based on player actions.

4. **Combat System**: Initiates and manages combat scenarios automatically based on the Grok narrative prompts.

5. **Experience and Levels**: Tracks experience points and levels, adjusting characters' abilities and stats accordingly.

6. **Custom Commands**: Contains specific bot commands for managing adventures and characters.

## Getting Started

1. **Installation**:
   - Ensure you have Python 3.6 or newer installed.
   - Install the dependencies using the command:
     ```
     pip install -r requirements.txt
     ```

2. **Setup**:
   - Copy `config_template.py` to `config.py` and fill in the required fields, especially your MariaDB and Telegram Bot credentials.

3. **Initialize Database**:
   - Run `create_database.py` to set up the database schema and populate initial data.

4. **Run the Bot**:
   - Use the command `python start_bot.py` to start the Telegram bot.
   - For debugging with mock responses: `python start_bot.py mock` (see MOCK_API_README.md for details)

## Commands

- `/start`: Start the bot.
- `/help`: Show available commands.
- `/generate`: Generate a new D&D character with random stats and equipment.
- `/startnewadventure`: Begin a new adventure (only if you have a character).
- `/terminateadventure`: End the current adventure (only for active participants).
- `/deletecharacter`: Remove your character (not allowed during active adventure).
- `/joinadventure`: Join an ongoing adventure.
- `/leaveadventure`: Exit an ongoing adventure (not allowed during combat).
- `/action <description>`: Describe your character's actions during an adventure.

## How to Play

1. **Create a Character**: Use `/generate` to create your D&D character. The bot will guide you through:
   - Rolling stats (4d6, drop lowest)
   - Choosing name, race, origin, and class
   - Selecting skills based on your class
   - Purchasing starting equipment

2. **Start an Adventure**: Use `/startnewadventure` to create a new adventure session. Other players can join using `/joinadventure`.

3. **Play the Adventure**: Once started, the Grok AI will generate an adventure introduction. Players describe their actions using `/action <description>`. When all players have submitted actions, the AI continues the story.

4. **Combat**: When combat begins (triggered by the AI), the bot automatically handles initiative order and turn-based combat with interactive buttons.

5. **Experience and Leveling**: Characters gain experience from adventures and combat, automatically leveling up when thresholds are reached.

## Features in Detail

- **Character Generation**: Full D&D 5e character creation with races, classes, origins, and equipment
- **AI Dungeon Master**: Grok AI generates dynamic adventures and responds to player actions
- **Combat System**: Turn-based combat with initiative, damage calculation, and victory conditions
- **Experience System**: Automatic XP tracking and character leveling
- **Persistent Data**: All character and adventure data stored in MariaDB database
- **Interactive UI**: Telegram inline keyboards for smooth character creation and combat
