const uint8_t PIN_CS = 10, PIN_SK = 13, PIN_DI = 11, PIN_DO = 12;
const uint8_t ADDR_BITS = 6;

void clk() { delayMicroseconds(5); digitalWrite(PIN_SK, HIGH); delayMicroseconds(5); digitalWrite(PIN_SK, LOW); }
void sendBits(uint16_t val, uint8_t n) { for (int8_t i = n - 1; i >= 0; i--) { digitalWrite(PIN_DI, (val >> i) & 1); clk(); } }
void csOn()  { digitalWrite(PIN_SK, LOW); digitalWrite(PIN_CS, HIGH); delayMicroseconds(5); }
void csOff() { digitalWrite(PIN_CS, LOW); digitalWrite(PIN_DI, LOW); delayMicroseconds(5); }

uint16_t readWord(uint8_t adr) {
  csOn(); sendBits(0b110, 3); sendBits(adr, ADDR_BITS);   // danach Dummy-0 an DO
  uint16_t v = 0;
  for (uint8_t i = 0; i < 16; i++) {
    delayMicroseconds(5); digitalWrite(PIN_SK, HIGH); delayMicroseconds(5);
    v = (v << 1) | digitalRead(PIN_DO); digitalWrite(PIN_SK, LOW);
  }
  csOff(); return v;
}
void ewen() { csOn(); sendBits(0b100, 3); sendBits(0b110000, ADDR_BITS); csOff(); }
void ewds() { csOn(); sendBits(0b100, 3); sendBits(0b000000, ADDR_BITS); csOff(); }

bool writeWord(uint8_t adr, uint16_t val) {
  ewen();
  csOn(); sendBits(0b101, 3); sendBits(adr, ADDR_BITS); sendBits(val, 16); csOff();
  csOn(); unsigned long t0 = millis(); bool ok = false;
  while (millis() - t0 < 50) { if (digitalRead(PIN_DO)) { ok = true; break; } }
  csOff(); ewds(); return ok;
}

void hex4(uint16_t v) { char b[6]; sprintf(b, "%04X ", v); Serial.print(b); }
void dump() {
  for (uint8_t row = 0; row < 64; row += 8) {
    char b[6]; sprintf(b, "%02X: ", row); Serial.print(b);
    uint16_t w[8];
    for (uint8_t i = 0; i < 8; i++) { w[i] = readWord(row + i); hex4(w[i]); }
    Serial.print(" |");
    for (uint8_t i = 0; i < 8; i++) { char hi = w[i] >> 8, lo = w[i] & 0xFF;
      Serial.print(isPrintable(hi) ? hi : '.'); Serial.print(isPrintable(lo) ? lo : '.'); }
    Serial.println("|");
  }
}

void setup() {
  pinMode(PIN_CS, OUTPUT); pinMode(PIN_SK, OUTPUT); pinMode(PIN_DI, OUTPUT); pinMode(PIN_DO, INPUT_PULLUP);
  digitalWrite(PIN_CS, LOW); digitalWrite(PIN_SK, LOW); digitalWrite(PIN_DI, LOW);
  Serial.begin(115200);
  Serial.println(F("93C46/AK93C45A ready: d | r <adr> | w <adr> <word>"));
}

void loop() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n'); line.trim();
  if (line.length() == 0) return;
  char cmd = line.charAt(0); unsigned int a = 0, v = 0;
  if (cmd == 'd') dump();
  else if (cmd == 'r' && sscanf(line.c_str() + 1, "%x", &a) == 1 && a < 64) { hex4(readWord(a)); Serial.println(); }
  else if (cmd == 'w' && sscanf(line.c_str() + 1, "%x %x", &a, &v) == 2 && a < 64) {
    bool ok = writeWord(a, v); uint16_t rb = readWord(a);
    Serial.print(ok ? F("write ok, readback ") : F("TIMEOUT, readback "));
    hex4(rb); Serial.println(rb == v ? F("(verify ok)") : F("(VERIFY FAILED)"));
  } else Serial.println(F("?  d | r <adr> | w <adr> <word>"));
}
