import os
import logging
import signal

# Set up logging
logging.basicConfig(level=logging.INFO)

class Bot:
    def __init__(self):
        self.initialize_configuration()
        self.setup_signal_handlers()
        logging.info('Bot initialized with configuration: %s', self.config)

    def initialize_configuration(self):
        self.config = {
            'task_queue': os.getenv('TASK_QUEUE', 'default_queue'),
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            'retry_limit': int(os.getenv('RETRY_LIMIT', '5'))
        }
        logging.getLogger().setLevel(self.config['log_level'])

    def setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def handle_signal(self, signum, frame):
        logging.info('Signal received: %s', signum)
        self.cleanup()
        exit(0)

    def cleanup(self):
        logging.info('Cleaning up resources...')

    def run(self):
        logging.info('Bot started running')
        # Implement task handling logic here

if __name__ == '__main__':
    bot = Bot()
    bot.run()