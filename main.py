import subprocess
import tempfile
import re
import requests
import telebot
from os import getenv


def extract_certificate_information(cert_pem):
	with tempfile.NamedTemporaryFile(delete=True) as temp_cert_file:
		temp_cert_file.write(cert_pem.encode())
		temp_cert_file.flush()
		result = subprocess.run(
			['openssl', 'x509', '-text', '-noout', '-in', temp_cert_file.name],
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True
		)
		if result.returncode != 0:
			raise RuntimeError(f"OpenSSL error: {result.stderr}")
		cert_text = result.stdout
	pattern = r"Serial Number:\s*([\da-f:]+)"
	match = re.search(pattern, cert_text, re.IGNORECASE)
	if match:
		serial_number = hex(int(match.group(1).replace(":", ""), 16)).split("0x")[1]
	else:
		return "Cannot find serial number"
	pattern = r"Subject: "
	match = re.search(pattern, cert_text, re.IGNORECASE)
	if match:
		subject = cert_text[match.end():].split("\n")[0]
	else:
		return "Cannot find subject"
	return [serial_number, subject]


def common_handler(message):
	if message.reply_to_message and message.reply_to_message.document:
		document = message.reply_to_message.document
	elif message.document:
		document = message.document
	else:
		bot.reply_to(message, "Please reply to a message with a keybox file or send a keybox file")
		return None
	file_info = bot.get_file(document.file_id)
	file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(API_TOKEN, file_info.file_path))
	certificate = extract_certificate_information(file.text.split("<Certificate format=\"pem\">")[1].split("</Certificate>")[0])
	reply = f"Serial Number: `{certificate[0]}`\nSubject: `{certificate[1]}`"
	try:
		status = get_google_sn_list()['entries'][certificate[0]]
		reply += f"\nSerial number found in Google's revoked keybox list\nReason: `{status['reason']}`"
	except KeyError:
		if certificate[0] == "4097":
			reply += "\nAOSP keybox found, this keybox is untrusted"
		else:
			reply += "\nSerial number not found in Google's revoked keybox list"
	bot.reply_to(message, reply, parse_mode='Markdown')


def get_google_sn_list():
	url = "https://android.googleapis.com/attestation/status"
	response = requests.get(
		url,
		headers={
			"Cache-Control": "max-age=0, no-cache, no-store, must-revalidate",
			"Pragma": "no-cache",
			"Expires": "0",
		}
	).json()
	return response


API_TOKEN = getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	bot.reply_to(message, "Send me keybox file and I will check if it's revoked")


@bot.message_handler(content_types=['document'])
def handle_document(message):
	common_handler(message)


@bot.message_handler(commands=['keybox'])
def handle_keybox(message):
	common_handler(message)


bot.infinity_polling()
