// Firmware pembaca RFID untuk ESP32 DevKit V1 30-pin + RC522 (MFRC522).
// Wiring (semua pin RC522 ke deretan KANAN ESP32, USB Micro USB di bawah):
//   RC522 SDA  -> D5   (GPIO5)   | RC522 RST  -> D22 (GPIO22)
//   RC522 SCK  -> D18  (GPIO18)  | RC522 3.3V -> 3V3 (JANGAN 5V/VIN)
//   RC522 MOSI -> D23  (GPIO23)  | RC522 GND  -> GND
//   RC522 MISO -> D19  (GPIO19)  | RC522 IRQ  -> tidak dicolok
// Output: hanya UID hex huruf besar, satu baris, 115200 baud (contoh: 3A257283).
// Flask (serial_listener.py) membaca baris itu dan memasukkannya ke antrean
// yang sama dengan Simulasi Tap. Jangan buka Serial Monitor saat Flask jalan,
// karena keduanya rebutan port COM yang sama.
#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN  5
#define RST_PIN 22

MFRC522 mfrc522(SS_PIN, RST_PIN);

void setup() {
  Serial.begin(115200);
  SPI.begin(18, 19, 23, SS_PIN);
  mfrc522.PCD_Init();
}

void loop() {
  if (!mfrc522.PICC_IsNewCardPresent()) { delay(50); return; }
  if (!mfrc522.PICC_ReadCardSerial()) { delay(50); return; }

  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(mfrc522.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  Serial.println(uid);

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(1000);
}
