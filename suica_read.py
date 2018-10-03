#!/usr/bin/env python
# -*- coding: utf-8 -*-
 
import csv
import binascii
import os
import struct
import sys
import nfc
import datetime
import fcntl

num_blocks = 20
service_code = 0x090f
 
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
    for station in cls.get_db("StationCode.csv"):
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
    self.process = self.get_process(row_be[1])
    self.category_h = self.get_category_h(row_be[1])
    self.category_l = self.get_category_l(row_be[1])
    self.year = self.get_year(row_be[3])
    self.month = self.get_month(row_be[3])
    self.day = self.get_day(row_be[3])
    self.balance = row_le[8]
    self.record_id = row_be[9] * 65536 + row_be[10]
    self.region = row_be[11]
 
    self.in_station = StationRecord.get_station(row_be[4], row_be[5])
    self.out_station = StationRecord.get_station(row_be[6], row_be[7])
 
  @classmethod
  def get_console(cls, key):
    # よく使われそうなもののみ対応
    return {
      0x03: "精算機",
      0x04: "携帯型端末",
      0x05: "車載端末",
      0x12: "券売機",
      0x16: "改札機",
      0x1c: "乗継精算機",
      0xc8: "自販機",
    }.get(key)
  @classmethod
  def get_process(cls, key):
    # よく使われそうなもののみ対応
    return {
      0x01: "運賃支払",
      0x02: "チャージ",
      0x0f: "バス",
      0x46: "物販",
    }.get(key)
  @classmethod
  def get_category_h(cls, key):
    # よく使われそうなもののみ対応
    return {
      0x01: "交通費",
      0x02: "その他入金",
      0x0f: "交通費",
      0x46: "食費",
    }.get(key)
  @classmethod
  def get_category_l(cls, key):
    # よく使われそうなもののみ対応
    return {
      0x01: "電車",
      0x02: "",
      0x0f: "バス",
      0x46: "食料品",
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
      filename = "NFC-%s.csv" % id
      content = ["計算対象,日付,内容,金額(円),保有金融機関,大項目,中項目,メモ\n"]
      if os.path.exists(filename):
        with open(filename) as f:
          content = f.readlines()

      last_history = None
      for i in range(num_blocks-1, -1, -1):
        bc = nfc.tag.tt3.BlockCode(i,service=0)
        data = tag.read_without_encryption([sc],[bc])
        history = HistoryRecord(bytes(data))
        if not last_history is None:
          diff = history.balance - last_history.balance
          detail = "#%d %s" % (history.record_id, history.console)
          if history.in_station.station_value != "" and history.out_station.station_value != "":
            detail += " %s→%s" % (history.in_station.station_value, history.out_station.station_value)
          # detail += " "
          # detail += "".join(['%02x' % s for s in data])
          line = '1,20%02d/%02d/%02d,%s,%d,手入力,%s,%s,"%s"' % (history.year, history.month, history.day, history.process, diff, history.category_h, history.category_l, detail)
          print(line)
          line += "\n"
          if not line in content:
            content.append(line)
        last_history = history

      with open(filename, mode='w') as f:
        f.writelines(content)

      print(filename)
    except Exception as e:
      print("error: %s" % e)
  else:
    print("error: tag isn't Type3Tag")
 
if __name__ == "__main__":
  lockfilePath = '/tmp/suica_read.lock'
  with open(lockfilePath , "w") as lockFile:
    try:
      fcntl.flock(lockFile, fcntl.LOCK_EX | fcntl.LOCK_NB)
      clf = nfc.ContactlessFrontend('usb')
      clf.connect(rdwr={'on-connect': connected})
    except IOError:
      print('process already exists')
