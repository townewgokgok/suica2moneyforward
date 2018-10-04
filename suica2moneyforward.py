#!/usr/bin/env python
# -*- coding: utf-8 -*-
 
import csv
import binascii
import os
import struct
import sys
import nfc
import datetime
import json
import fcntl

num_blocks = 20
service_code = 0x090f
here = os.path.dirname(os.path.abspath(__file__))
 
class StationRecord(object):
  db = None
 
  def __init__(self, row):
    self.area_key = int(row[0], 10)
    self.line_key = int(row[1], 10)
    self.station_key = int(row[2], 10)
    self.company_value = row[3]
    self.line_value = row[4]
    self.station_value = row[5]
 
  @classmethod
  def get_none(cls):
    # 駅データが見つからないときに使う
    return cls(["0", "0", "0", "", "", ""])
  @classmethod
  def get_db(cls, filename):
    # 駅データのcsvを読み込んでキャッシュする
    if cls.db == None:
      cls.db = []
      for row in csv.reader(open(filename, 'rU'), delimiter=',', dialect=csv.excel_tab):
        cls.db.append(cls(row))
    return cls.db
  @classmethod
  def get_station(cls, line_key, station_key):
    # 線区コードと駅コードに対応するStationRecordを検索する
    for station in cls.get_db(here+'/StationCode.csv'):
      if station.line_key == line_key and station.station_key == station_key:
        return station
    return cls.get_none()
 
class HistoryRecord(object):
  def __init__(self, data):
    # ビッグエンディアンでバイト列を解釈する
    row_be = struct.unpack('>2B2H4BHBHB', data)
    # リトルエンディアンでバイト列を解釈する
    row_le = struct.unpack('<2B2H4BHBHB', data)
 
    self.db = None
    self.console = self.get_console(row_be[0])
    self.process = self.get_process(row_be[1])[0]
    self.category_h = self.get_process(row_be[1])[1]
    self.category_l = self.get_process(row_be[1])[2]
    self.year = self.get_year(row_be[3])
    self.month = self.get_month(row_be[3])
    self.day = self.get_day(row_be[3])
    self.balance = row_le[8]
    self.record_id = row_be[9] * 65536 + row_be[10]
    self.region = row_be[11]
 
    if not row_be[0] in [5, 199, 200]:
      self.in_station = StationRecord.get_station(row_be[4], row_be[5])
      self.out_station = StationRecord.get_station(row_be[6], row_be[7])
    else:
      self.in_station = None
      self.out_station = None
 
  @classmethod
  def get_console(cls, key):
    return {
      3: '精算機',
      4: '携帯型端末',
      5: '車載端末',
      7: '券売機',
      8: '券売機',
      9: '入金機',
      18: '券売機',
      20: '券売機等',
      21: '券売機等',
      22: '改札機',
      23: '簡易改札機',
      24: '窓口端末',
      25: '窓口端末',
      26: '改札端末',
      27: '携帯電話',
      28: '乗継精算機',
      29: '連絡改札機',
      31: '簡易入金機',
      70: 'VIEW ALTTE',
      72: 'VIEW ALTTE',
      199: '物販端末',
      200: '自販機'
    }.get(key)
  @classmethod
  def get_process(cls, key):
    return {
      1: ['運賃支払(改札出場)', '交通費', '電車'],
      2: ['チャージ', 'その他入金', ''],
      3: ['券購(磁気券購入)', '交通費', '電車'],
      4: ['精算', '交通費', '電車'],
      5: ['精算(入場精算)', '交通費', '電車'],
      6: ['窓出(改札窓口処理)', '交通費', '電車'],
      7: ['新規(新規発行)', 'その他入金', ''],
      8: ['控除(窓口控除)', 'その他入金', ''],
      13: ['バス(PiTaPa系)', '交通費', 'バス'],
      15: ['バス(IruCa系)', '交通費', 'バス'],
      17: ['再発(再発行処理)', 'その他入金', ''],
      19: ['支払(新幹線利用)', '交通費', '電車'],
      20: ['入A(入場時オートチャージ)', 'その他入金', ''],
      21: ['出A(出場時オートチャージ)', 'その他入金', ''],
      31: ['入金(バスチャージ)', 'その他入金', ''],
      35: ['券購(バス路面電車企画券購入)', '交通費', 'バス'],
      70: ['物販', '食費', '食料品'],
      72: ['特典(特典チャージ)', 'その他入金', ''],
      73: ['入金(レジ入金)', 'その他入金', ''],
      74: ['物販取消', 'その他入金', ''],
      75: ['入物(入場物販)', '食費', '食料品'],
      198: ['物現(現金併用物販)', '食費', '食料品'],
      203: ['入物(入場現金併用物販)', '食費', '食料品'],
      132: ['精算(他社精算)', '交通費', '電車'],
      133: ['精算(他社入場精算)', '交通費', '電車']
    }.get(key)
  @classmethod
  def get_year(cls, date):
    return (date >> 9) & 0x7f
  @classmethod
  def get_month(cls, date):
    return (date >> 5) & 0x0f
  @classmethod
  def get_day(cls, date):
    return (date >> 0) & 0x1f
 
def connected(tag):
  if isinstance(tag, nfc.tag.tt3.Type3Tag):
    try:
      sc = nfc.tag.tt3.ServiceCode(service_code >> 6 ,service_code & 0x3f)
      id = binascii.hexlify(tag.identifier).upper()
      csvfile = "NFC-%s.csv" % id
      statefile = "NFC-%s.json" % id

      state = {'balance': 0, 'record_id': 0}
      if os.path.exists(statefile):
        with open(statefile) as f:
          state = json.load(f)

      content = ["計算対象,日付,内容,金額(円),保有金融機関,大項目,中項目,メモ\n"]
      if os.path.exists(csvfile):
        with open(csvfile) as f:
          content = f.readlines()

      last_history = None
      dirty = False
      for i in range(num_blocks-1, -1, -1):
        bc = nfc.tag.tt3.BlockCode(i,service=0)
        data = tag.read_without_encryption([sc],[bc])
        history = HistoryRecord(bytes(data))
        if not last_history is None:
          diff = history.balance - last_history.balance
          detail = "#%d %s" % (history.record_id, history.console)
          if not history.in_station is None or not history.out_station is None:
            detail += " %s→%s" % (history.in_station.station_value, history.out_station.station_value)
          # detail += " "
          # detail += "".join(['%02x' % s for s in data])
          line = '1,20%02d/%02d/%02d,%s,%d,手入力,%s,%s,"%s"' % (history.year, history.month, history.day, history.process, diff, history.category_h, history.category_l, detail)
          line += "\n"
          if not line in content and state['record_id'] < history.record_id:
            if not dirty:
              sys.stdout.write(content[0])
            sys.stdout.write(line)
            content.append(line)
            dirty = True
        last_history = history

      if not dirty:
        print("no update")
        return

      with open(csvfile, mode='w') as f:
        f.writelines(content)

      if not last_history is None:
        state['balance'] = last_history.balance
        state['record_id'] = last_history.record_id
      with open(statefile, 'w') as f:
        json.dump(state, f)

      print("")
      print("updated %s" % csvfile)
      print("updated %s" % statefile)
    except Exception as e:
      print("error: %s" % e)
  else:
    print("error: tag isn't Type3Tag")

if __name__ == "__main__":
  lockfilePath = '/tmp/suica2moneyforward.lock'
  with open(lockfilePath , "w") as lockFile:
    try:
      fcntl.flock(lockFile, fcntl.LOCK_EX | fcntl.LOCK_NB)
      clf = nfc.ContactlessFrontend('usb')
      clf.connect(rdwr={'on-connect': connected})
    except IOError:
      print('process already exists')
