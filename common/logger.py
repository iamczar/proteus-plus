import logging


class Logger:

    def __init__(self, logger_name, log_filename, log_level, log_to_console=True, log_to_file=False):

        self.logger_name = logger_name
        self.filename = log_filename
        self.logLevel = log_level

        formatter = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
        self.logger = logging.getLogger(self.logger_name)

        logLevel = 0
        if("info" == self.logLevel):
            logLevel = logging.INFO
        elif("warn" == self.logLevel):
            logLevel = logging.WARN
        elif("critical" == self.logLevel):
            logLevel = logging.CRITICAL
        elif("error" == self.logLevel):
            logLevel = logging.ERROR
        elif("debug" == self.logLevel):
            logLevel = logging.DEBUG
        else:
            logLevel = logging.DEBUG

        if(True == log_to_file):
            print(F"{self.logger_name} log_to_file is enabled")
            file_handler = logging.FileHandler(self.filename)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        if(True == log_to_console):
            print(F"{self.logger_name} log_to_console is enabled")
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        self.logger.setLevel(logLevel)

    def info(self, message):
        self.logger.info(message)

    def warn(self, message):
        self.logger.warn(message)

    def error(self, message):
        self.logger.error(message)

    def debug(self, message):
        self.logger.debug(message)