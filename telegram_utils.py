import logging
from typing import List
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

TELEGRAM_MAX_MESSAGE_LENGTH = 4096

def split_long_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Splits a long message into chunks that fit within Telegram's message limit.
    Tries to split on natural boundaries like paragraphs and sentences.
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    remaining_text = text
    
    while len(remaining_text) > max_length:
        # Try to find a good split point
        chunk = remaining_text[:max_length]
        
        # Look for paragraph breaks first (double newlines)
        last_paragraph = chunk.rfind('\n\n')
        if last_paragraph > max_length * 0.7:  # Don't split too early in the chunk
            split_point = last_paragraph + 2
        else:
            # Look for single newlines
            last_newline = chunk.rfind('\n')
            if last_newline > max_length * 0.7:
                split_point = last_newline + 1
            else:
                # Look for sentence endings
                last_sentence = max(chunk.rfind('. '), chunk.rfind('! '), chunk.rfind('? '))
                if last_sentence > max_length * 0.7:
                    split_point = last_sentence + 2
                else:
                    # Look for word boundaries
                    last_space = chunk.rfind(' ')
                    if last_space > max_length * 0.7:
                        split_point = last_space + 1
                    else:
                        # Last resort: hard split
                        split_point = max_length
        
        chunks.append(remaining_text[:split_point].strip())
        remaining_text = remaining_text[split_point:].strip()
    
    if remaining_text:
        chunks.append(remaining_text)
    
    logger.info(f"Split message into {len(chunks)} chunks. Original length: {len(text)}")
    return chunks

async def send_long_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, 
                           parse_mode: str = None, reply_markup=None):
    """
    Sends a potentially long message, splitting it if necessary.
    Only the last chunk gets the reply markup.
    """
    chunks = split_long_message(text)
    
    logger.info(f"Sending message in {len(chunks)} chunks")
    
    for i, chunk in enumerate(chunks):
        is_last_chunk = (i == len(chunks) - 1)
        chunk_reply_markup = reply_markup if is_last_chunk else None
        
        if hasattr(update, 'callback_query') and update.callback_query:
            # If this is a callback query, edit the first message and send new ones for the rest
            if i == 0:
                await update.callback_query.edit_message_text(
                    chunk, 
                    parse_mode=parse_mode,
                    reply_markup=chunk_reply_markup
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=chunk,
                    parse_mode=parse_mode,
                    reply_markup=chunk_reply_markup
                )
        else:
            # Regular message
            await update.message.reply_text(
                chunk,
                parse_mode=parse_mode,
                reply_markup=chunk_reply_markup
            )

async def edit_long_message(query, text: str, parse_mode: str = None, reply_markup=None):
    """
    Edits a message with potentially long text, splitting if necessary.
    """
    chunks = split_long_message(text)
    
    logger.info(f"Editing message with {len(chunks)} chunks")
    
    for i, chunk in enumerate(chunks):
        is_last_chunk = (i == len(chunks) - 1)
        chunk_reply_markup = reply_markup if is_last_chunk else None
        
        if i == 0:
            # Edit the original message
            await query.edit_message_text(
                chunk,
                parse_mode=parse_mode,
                reply_markup=chunk_reply_markup
            )
        else:
            # Send additional messages
            await query.message.reply_text(
                chunk,
                parse_mode=parse_mode,
                reply_markup=chunk_reply_markup
            )
