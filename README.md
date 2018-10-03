# 概要

PaSoRi に Suica や PASMO をかざすと履歴を読み取り、マネーフォワードにインポートできる形式のCSVとして保存します。

https://github.com/m2wasabi/nfcpy-suica-sample を改変したものです。

# 注意事項

- 残額履歴の差額から支出・チャージ額を抽出するため、履歴中の最も古いレコードはCSVに記録されません。
- 駅名表を更新していないので、CSV中の駅名は間違っている可能性があります。

# ライセンス

MIT License
