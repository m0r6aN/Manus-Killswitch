from loguru import logger
logger.remove()  # Remove default logger
logger.add("../app/logs/squad.log", level="INFO", format="{time} - {level} - {message}", rotation="1 MB") 
logger.info("Websocket Server Initialized")