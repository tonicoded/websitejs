import logging
import requests
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime, timedelta
import json
from git import Repo


REPO_PATH = "C:/Users/antho/OneDrive/Bureaublad/tgbot/website1"


def push_to_github():
    try:
        repo = Repo(REPO_PATH)
        # Check if there are changes to commit
        if repo.is_dirty(untracked_files=True):
            repo.git.add('NNNchallengers.txt')
            repo.index.commit("Automated update of NNNchallengers.txt")
            origin = repo.remote(name='origin')
            origin.push()
            logging.info(f"Updated and pushed NNNchallengers.txt to GitHub.")
        else:
            logging.info("No changes to commit.")
    except Exception as e:
        logging.error(f"Error while pushing to GitHub: {e}")



# Bot token and BaseScan API key
BOT_TOKEN = '7604430191:AAFGvJdycEQgMhj5fTLCPK0UsXzPxLmt5Fw'
GROUP_CHAT_ID = -1002478930803
BASESCAN_API_KEY = '5A29HRJGYX22NNGPHRNM57KZIYM9646MWP'
TOKEN_ADDRESS = '0x20895e16d5ae9d6e0ca127ed093a7cbe65dcb018'

# In-memory storage for participants and the scoreboard
participants = {}

# File for saving participants
FILENAME = 'NNNchallengers.txt'

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def save_participant_to_file():
    with open(FILENAME, 'w') as file:
        for user_id, info in participants.items():
            file.write(f"{user_id},{info['name']},{info['wallet']},{info['start_time']}\n")
    # Push the updated file to GitHub
    push_to_github()
def update_loop():
    while True:
        push_to_github()  # Check and push every 10 seconds
        time.sleep(10)


# Load participant info from the file
def load_participants_from_file():
    try:
        with open(FILENAME, 'r') as file:
            for line in file:
                user_id, name, wallet, start_time = line.strip().split(',')
                participants[int(user_id)] = {'name': name, 'wallet': wallet, 'start_time': float(start_time)}
    except FileNotFoundError:
        pass  # If file doesn't exist yet, just continue

# Calculate how long a user has been in the challenge
def calculate_duration(start_time):
    elapsed_time = time.time() - start_time
    days = int(elapsed_time // (24 * 3600))
    hours = int((elapsed_time % (24 * 3600)) // 3600)
    minutes = int((elapsed_time % 3600) // 60)
    return days, hours, minutes

# Restrict certain commands to private chat only
async def check_private_chat(update: Update):
    if update.message.chat.type != 'private':
        await update.message.reply_text("Please use this command in a private chat with the bot.")
        return False
    return True

# Restrict certain commands to the group chat only
async def check_group_chat(update: Update):
    if update.message.chat.id != GROUP_CHAT_ID:
        await update.message.reply_text("This command can only be used in the group chat.")
        return False
    return True

# Handle /start command (private only)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private_chat(update):
        return

    user = update.effective_user
    welcome_message = (
        f"Welcome {user.first_name}! You're about to embark on the No Nut November (NNN) Challenge!\n"
        "Can you resist for an entire month?\n"
        "Commands:\n"
        "/accept [wallet_address] - Join the challenge and verify your token ownership\n"
        "/info - Check your current progress (group only)\n"
        "/scoreboard - View the leaderboard (group only)\n"
        "/failed - If you give in, reset your progress and try again"
    )
    await update.message.reply_text(welcome_message)

# Verify if the user holds the required token
def verify_token_ownership(wallet_address):
    url = f"https://api.basescan.org/api?module=account&action=tokenbalance&contractaddress={TOKEN_ADDRESS}&address={wallet_address}&tag=latest&apikey={BASESCAN_API_KEY}"
    response = requests.get(url).json()

    if response['status'] == '1':
        balance = int(response['result']) / (10 ** 18)  # Convert balance from Wei to token units
        if balance >= 50000:  # Check if the balance is at least 50k tokens
            return True
    return False

# Handle /accept command (private only)
async def accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private_chat(update):
        return

    user = update.effective_user

    # Check if the user is already a participant
    if user.id in participants:
        await update.message.reply_text("You're already in the challenge! Use /failed to reset if needed.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Please provide a wallet address. Usage: /accept [wallet_address]")
        return

    wallet_address = context.args[0]

    # Ensure the wallet isn't already used by another user
    if any(info['wallet'] == wallet_address for info in participants.values()):
        await update.message.reply_text("This wallet address has already been used by another participant.")
        return

    await update.message.reply_text("Verifying your token ownership...")

    # Verify token ownership using BaseScan
    if verify_token_ownership(wallet_address):
        start_time = time.time()  # Store the current time when they join
        participants[user.id] = {'name': user.first_name, 'wallet': wallet_address, 'start_time': start_time}
        save_participant_to_file()
        await update.message.reply_text("You have successfully joined the challenge! The clock is ticking...")
        # Announce in group chat
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"{user.first_name} has joined the NNN Challenge! Let's see if they can make it!"
        )
    else:
        await update.message.reply_text("Verification failed. Make sure you own at least 50k tokens.")

# Handle /failed command (private only)
async def failed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_private_chat(update):
        return

    user = update.effective_user

    if user.id not in participants:
        await update.message.reply_text("You're not part of the challenge.")
        return

    # Remove the user from the challenge and announce it
    participants.pop(user.id, None)
    save_participant_to_file()
    await update.message.reply_text("You have left the challenge.")
    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"{user.first_name} has given in to temptation and left the NNN Challenge!"
    )

# Handle /info command (group only)
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group_chat(update):
        return

    user = update.effective_user

    if user.id not in participants:
        await update.message.reply_text("You're not part of the challenge.")
    else:
        participant_info = participants[user.id]
        days, hours, minutes = calculate_duration(participant_info['start_time'])
        await update.message.reply_text(
            f"Status: Still holding strong!\n"
            f"Time in challenge: {days} days, {hours} hours, {minutes} minutes"
        )

# Handle /scoreboard command (group only)
async def scoreboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group_chat(update):
        return

    if not participants:
        await update.message.reply_text("No participants yet.")
    else:
        scoreboard_message = "NNN Challenge Scoreboard:\n"
        for user_id, info in participants.items():
            days, hours, minutes = calculate_duration(info['start_time'])
            scoreboard_message += f"{info['name']}: {days} days, {hours} hours, {minutes} minutes\n"
        await update.message.reply_text(scoreboard_message)

# Remove user if they sold all their tokens
async def check_token_balance(context: ContextTypes.DEFAULT_TYPE):
    for user_id, info in list(participants.items()):
        wallet_address = info['wallet']
        if not verify_token_ownership(wallet_address):
            # Remove the user if they don't own enough tokens
            participants.pop(user_id, None)
            save_participant_to_file()
            logger.info(f"Removed {info['name']} for selling tokens.")
            # Announce in group chat
            await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"{info['name']} has been removed from the NNN Challenge for selling their tokens."
            )

def main():
    # Load participants from file at startup
    load_participants_from_file()

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("accept", accept))
    application.add_handler(CommandHandler("failed", failed))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("scoreboard", scoreboard))

    # Periodically check participants' token balances to remove them if necessary
    application.job_queue.run_repeating(check_token_balance, interval=60, first=10)
    update_loop()  # Start the loop to push to GitHub every 10 seconds
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
