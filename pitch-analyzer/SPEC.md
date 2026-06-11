# 日本語朗読音声ピッチ分析ツール 仕様書(案)

バージョン: 0.1(ドラフト)
作成日: 2026-06-11

## 1. 目的

日本語の朗読音声を、対応する朗読テキストを手がかりに**アクセント句単位**に分割し、
各アクセント句の**正規化済み F0(基本周波数)**を出力する研究用ツールを提供する。

想定ユーザー: 音声・韻律研究者(本人)。Praat 等での追加分析・可視化につなげられること。

## 2. 入力

| 項目 | 形式 | 備考 |
|------|------|------|
| 朗読音声 | WAV(モノラル推奨、16kHz 以上) | ステレオは自動で 1ch にミックスダウン。MP3 等は ffmpeg があれば自動変換 |
| 朗読テキスト | UTF-8 プレーンテキスト(.txt) | 1ファイル=1音声に対応。文単位の改行を推奨(必須ではない) |

- 単一ファイルのペア指定と、ディレクトリ一括処理(同名の `.wav` / `.txt` をペアリング)の両方に対応する。
- テキストは漢字かな交じりで可。読みの推定は形態素解析に委ねるが、読み誤りが懸念される箇所
  (数字・固有名詞など)のために、**読み指定の上書き(ふりがな注記)**をオプションで受け付ける
  (例: `{山梨|やまなし}` 形式)。

## 3. 処理パイプライン

```
テキスト ──► (1) 言語処理: 形態素解析 + アクセント句推定(pyopenjtalk)
                │  → モーラ列・音素列・アクセント句境界・アクセント核位置
音声   ──► (2) F0 抽出(WORLD harvest + stonemask、フレーム 5ms)
                │
        (3) 強制アラインメント: 音素列 ⇔ 音声 の時刻対応付け
                │  → 音素境界時刻 → アクセント句の開始/終了時刻
        (4) アクセント句ごとの F0 切り出し
                │
        (5) 正規化(後述)
                │
        (6) 出力(CSV / JSON / TextGrid / PNG)
```

### (1) 言語処理

- `pyopenjtalk` のフルコンテキストラベルから以下を取得する:
  - アクセント句(AP)境界、各 AP のモーラ数、アクセント核位置(0型=平板 など)
  - 音素列(アラインメント用)
- ポーズ(句読点・改行)はアクセント句境界として扱い、`pau` として音素列に含める。

### (2) F0 抽出

- 既定: WORLD(`pyworld`)の harvest + stonemask。フレームシフト 5 ms。
- 代替(オプション): `praat-parselmouth`(autocorrelation 法)。研究上の比較用。
- F0 探索範囲は既定 60–500 Hz。話者に応じて `--f0-floor/--f0-ceil` で変更可能。
- 無声区間・無声化母音は F0 = 0(欠損)として保持する。**既定では補間しない**
  (オプション `--interpolate` で AP 内の欠損を線形補間)。

### (3) 強制アラインメント

- 推奨: **Montreal Forced Aligner(MFA)+ japanese_mfa モデル**。
  - pyopenjtalk の読み(カナ)から MFA 用の発音を生成して辞書登録する。
- 代替: Julius 音素セグメンテーションキット(MFA が導入できない環境向け)。
- アラインメント結果(音素境界)を AP 境界に集約し、各 AP の `[t_start, t_end]` を確定する。
- **品質チェック**: テキストと音声の不一致(読み飛ばし・言い直し)が疑われる箇所は、
  音素尤度の低さ・極端な音素長を手がかりに警告を出し、該当 AP に `low_confidence` フラグを付ける。

### (4) アクセント句ごとの切り出し

- 各 AP について F0 系列(時刻, Hz)を切り出す。前後のポーズは含めない。
- AP 内のモーラ境界時刻も保持する(モーラ単位の事後分析を可能にするため)。

### (5) 正規化

複数の正規化を**併記して**出力する(研究目的により使い分けるため):

1. **半音変換(話者正規化)**: `f0_st = 12 * log2(F0 / F0_ref)`
   - `F0_ref` は既定で「ファイル全体の有声フレームの F0 幾何平均」。
     `--ref speaker`(複数ファイルの同一話者平均)/ `--ref value:120` 等で変更可。
2. **z スコア(log 領域)**: `f0_z = (log F0 − μ) / σ`(μ, σ はファイルまたは話者単位)
3. **時間正規化輪郭**: 各 AP の F0 を等間隔 N 点(既定 N=30)にリサンプリングした
   半音値の輪郭。AP 間の長さ差を除いた形状比較用。

## 4. 出力

出力先ディレクトリに以下を生成する:

| ファイル | 内容 |
|---------|------|
| `<name>_frames.csv` | フレーム単位のロング形式: `file, ap_index, ap_text, mora_index, time_sec, f0_hz, f0_st, f0_z, voiced` |
| `<name>_ap_summary.csv` | AP 単位の要約: `ap_index, ap_text, ap_kana, accent_type, mora_count, t_start, t_end, duration, f0_mean_st, f0_max_st, f0_min_st, f0_range_st, peak_time_ratio, voiced_ratio, low_confidence` |
| `<name>_ap_contours.csv` | 時間正規化輪郭: `ap_index, point_1 … point_N`(半音値) |
| `<name>.json` | 上記すべてを含む構造化データ(階層: 文 > アクセント句 > モーラ) |
| `<name>.TextGrid` | Praat 用。tier: phones / moras / accent_phrases(検証・手修正用) |
| `<name>_f0.png`(オプション) | F0 曲線+AP 境界+AP テキストの可視化 |

- 文字コードはすべて UTF-8。CSV は Excel 互換のため BOM 付きオプションあり。
- アラインメントを**手修正した TextGrid を再入力**して、(4)以降だけ再実行できること
  (`--from-textgrid` オプション)。研究上、自動アラインメントの誤りの修正は必須になるため。

## 5. CLI 設計

```
# 単一ファイル
pitchan analyze --wav recording.wav --text script.txt --out results/

# 一括処理
pitchan batch --dir data/ --out results/

# 手修正済み TextGrid から再計算
pitchan analyze --wav recording.wav --from-textgrid fixed.TextGrid --out results/

主なオプション:
  --f0-floor/--f0-ceil   F0 探索範囲 [Hz](既定 60/500)
  --frame-shift          フレームシフト [ms](既定 5)
  --ref                  半音変換の基準(file / speaker / value:<Hz>)
  --norm-points N        時間正規化の点数(既定 30)
  --interpolate          AP 内の無声区間を線形補間
  --plot                 PNG 可視化を出力
  --aligner              mfa / julius(既定 mfa)
```

## 6. 技術スタック

- Python 3.10+
- `pyopenjtalk`(アクセント句・読み推定)/ `pyworld`(F0)/ `numpy`, `pandas`
- Montreal Forced Aligner(conda 導入)+ `japanese_mfa` 音響モデル・辞書
- `praatio` または `textgrid`(TextGrid 入出力)/ `matplotlib`(可視化)
- パッケージ構成: `pitch-analyzer/` 配下に `pyproject.toml` を置く独立パッケージ
  (本リポジトリ=GitHub Pages サイトとは独立に pip インストール可能とする)

## 7. エラー処理・既知の限界

- **読み誤り**: OpenJTalk の読み・アクセント推定は完全ではない。ふりがな注記(§2)と
  TextGrid 手修正(§4)で回避する設計とする。アクセント型自体の誤りは輪郭データには影響しない
  (境界とラベルのみ使用)が、`accent_type` 列の利用時は注意を促す。
- **不一致**: テキストと発話の不一致は警告+フラグで通知し、処理は継続する。
- **F0 抽出誤り**(倍ピッチ/半ピッチ): 探索範囲の調整で対処。オプションで
  メディアンフィルタ(5点)を提供。
- 複数話者が混在する音声、歌唱、自発音声(フィラー・言い淀み多数)は対象外。

## 8. 段階的実装計画

1. **Phase 1**: F0 抽出+pyopenjtalk による AP 推定+MFA アラインメント+CSV/JSON 出力(コア)
2. **Phase 2**: TextGrid 入出力・手修正再計算・可視化 PNG
3. **Phase 3**: 一括処理・話者単位正規化・ふりがな注記対応
4. **(将来)**: 出力 JSON をブラウザで閲覧する簡易ビューア(本 GitHub Pages 上に設置可能)

## 9. 未確定事項(要確認)

1. アラインメントは MFA で良いか(conda 環境の導入が必要)。Julius 代替を先に作るか。
2. 正規化の主目的は「話者間比較」か「同一話者内の文体・スタイル比較」か
   → 基準値(§5 `--ref`)の既定を file にするか speaker にするか。
3. 時間正規化の点数 N、AP より細かいモーラ単位輪郭の要否。
4. 想定データ規模(ファイル数・総時間)。大規模なら並列化を Phase 1 から入れる。
