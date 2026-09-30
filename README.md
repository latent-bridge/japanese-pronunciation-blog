# 日語發音筆記

繁体字で日本語発音を解説する静的ブログ。記事はMarkdownで管理し、利用者の最終確認後に公開します。

## 構成

Python 3.13とPython-MarkdownでHTMLを生成し、GitHub ActionsからGitHub Pagesへ公開します。DB・常時稼働サーバー・フロントエンドのJavaScriptは不要です。短い音声は確認後に `assets/audio/` へ置き、HTMLの `audio controls` で再生できます。

- `posts/` は利用者確認済みの記事と承認時のハッシュだけを保存します。
- `assets/` はCSS・アイコン・公開可能な素材を保存します。
- `scripts/build.py` は記事一覧・記事・紹介ページ・RSS・サイトマップを生成します。
- `scripts/check.py` は内部リンクと未確認記事の混入を検査します。
- `dist/` だけを配信します。未確認原稿はこの公開リポジトリの外に保存します。

## セットアップ

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/build.py
.venv/bin/python scripts/check.py dist --prefix /japanese-pronunciation-blog
```

## 記事を確認して公開する

1. 非公開の作業場所にMarkdown原稿を作ります。TOMLヘッダーを `+++` で囲み、`title`、`description`、`slug`、`topic`、`date`、`status = "review"` を指定します。日付は `"YYYY-MM-DD"` 形式です。
2. プレビューを生成し、利用者が内容と表示を確認します。

```sh
.venv/bin/python scripts/build.py --review /path/to/private/article.md --url http://127.0.0.1:8891
.venv/bin/python scripts/check.py preview --allow-preview
.venv/bin/python -m http.server 8891 --bind 127.0.0.1 --directory preview
```

ブラウザーで `http://127.0.0.1:8891/` を開きます。終了時はCtrl+Cで停止します。確認項目は語義・発音の説明・繁体字の自然さ・出典・解答・スマートフォンの表示。音声を加えるときは発音・台本との一致・利用権も確認します。

3. 利用者から明示的に公開可の返事を得た後、その原稿を取り込みます。下記の確認日は実際の日付に置き換えます。

```sh
.venv/bin/python scripts/approve.py /path/to/private/article.md --reviewed-on YYYY-MM-DD --user-confirmed
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/build.py
.venv/bin/python scripts/check.py dist --prefix /japanese-pronunciation-blog
git add posts
git commit -m "Publish reviewed article"
git push origin main
```

承認のハッシュは、確認後に本文が変わったことを検知するためのものです。ツールが利用者の意思を判定するものではありません。修正した記事も再確認・再取込みします。未確認原稿を公開リポジトリへコミットしないでください。

4. GitHub Actionsの `Check and publish blog` が成功し、公開URLの本文とリンクが正しいことを確認します。GitHubの設定でPagesのSourceをGitHub Actionsにします。

## 修正と戻し方

誤りを見つけた場合は修正文を確認して公開します。急ぎで元の状態に戻す場合は、対象の公開コミットを `git revert <commit>` し、生成・検査後にpushします。記事と `.approval.json` は同じコミットで戻します。Actionsの成功と公開ページの内容を確認してください。

## ホスティングを変更する場合

Cloudflare Pagesでも同じ静的HTMLを配信できます。ビルドコマンドは `python -m pip install -r requirements.txt && python scripts/build.py`、出力先は `dist`。Python 3.13以上を指定し、`site.toml` の `url` を実際のURLに変更します。独自ドメインやサイトのパスを変えるときは、CIのリンク検査の `--prefix` も合わせて変更してください。

## 計測

初期版は外部のアクセス解析を使いません。閲覧数・再訪率は未計測です。RSSは再訪の手段として提供し、購読者数を把握できるとは扱いません。GitHub Issuesは公開の訂正窓口であり、個人情報や録音を収集しません。
