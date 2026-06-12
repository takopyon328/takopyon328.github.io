# ニコニコ風コメントスクリーン(GitHub Pages版)

授業中に学生がスマホ・PCから送ったコメントを、教員PCの画面に
ニコニコ動画のように右から左へ流して表示するアプリの **Web版** です。

学生は GitHub Pages のURLにアクセスするだけなので、**学外やモバイル回線
からでも投稿できます**。教員PC側もブラウザでページを開くだけです。

> 💡 同じネットワーク内だけで完結させたい場合は、ローカルサーバー版
> ([comment-screen/](../comment-screen/))もあります。

```
学生のスマホ/PC ──> Firebase(無料) <── 教員PC
 投稿ページ          コメント中継      表示ページ(プロジェクターに映す)
 (GitHub Pages)                       (GitHub Pages)
```

リアルタイム通信の中継に Google の **Firebase(Cloud Firestore)** を
使います。無料枠(1日5万回読み取り・2万回書き込み)で授業利用には
十分足ります。クレジットカード登録も不要です。

## 初回セットアップ(最初に1回だけ)

### 1. Firebaseプロジェクトを作る

1. [Firebaseコンソール](https://console.firebase.google.com/) にGoogleアカウントでログイン
2. 「プロジェクトを作成」→ プロジェクト名は任意(例: `comment-screen`)
3. Googleアナリティクスは「無効」でOK → 作成

### 2. Webアプリを登録して設定をコピーする

1. プロジェクトのトップページで **`</>`(ウェブ)** アイコンをクリック
2. アプリのニックネームは任意(例: `comment`)→「アプリを登録」
   (Firebase Hosting のチェックは不要)
3. 表示されるコードの中の `const firebaseConfig = { ... }` の中身を、
   このフォルダの **`firebase-config.js`** の該当箇所に貼り付ける

```js
export const firebaseConfig = {
  apiKey: "AIzaSy...",          // ← コンソールに表示された値に置き換える
  authDomain: "xxx.firebaseapp.com",
  projectId: "xxx",
  storageBucket: "xxx.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abc..."
};
```

※ この apiKey は「公開してよい識別子」で、秘密鍵ではありません。
アクセス制限は次の手順のセキュリティルールで行います。

### 3. Firestoreデータベースを作る

1. 左メニューの「構築」→「Firestore Database」→「データベースを作成」
2. ロケーションは `asia-northeast1`(東京)を選択
3. 「本番環境モード」で作成
4. 作成後、「ルール」タブを開き、以下に**全て置き換えて**「公開」

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /rooms/{room}/comments/{commentId} {
      // 誰でもコメントの読み取りと投稿ができる(編集・削除は不可)
      allow read: if true;
      allow create: if request.resource.data.keys().hasOnly(['text', 'color', 'size', 'ts'])
        && request.resource.data.text is string
        && request.resource.data.text.size() > 0
        && request.resource.data.text.size() <= 200
        && request.resource.data.color is string
        && request.resource.data.color.size() <= 10
        && request.resource.data.size in ['small', 'medium', 'large']
        && request.resource.data.ts == request.time;
      allow update, delete: if false;
    }
  }
}
```

### 4. GitHubにプッシュして公開する

`firebase-config.js` の変更をコミットして main ブランチにプッシュすると、
数分でGitHub Pagesに反映されます。

## 授業での使い方

1. **教員PC**: ブラウザで
   `https://takopyon328.github.io/comment/screen.html` を開き、
   プロジェクターに映す(Fキーで全画面)
2. **学生**: 画面右下に表示されるURL/QRコードからアクセスして投稿
   - 投稿ページ: `https://takopyon328.github.io/comment/`
   - コメントの色(7色)と大きさ(小・中・大)を選べます

### 表示ページのキー操作

| キー | 動作 |
|---|---|
| F | 全画面表示の切り替え |
| H | 右下の案内(URL・QRコード)の表示/非表示 |
| C | 流れているコメントを全て消す |

### オプション(URLパラメータ)

- **授業ごとにルームを分ける**: 両方のURLに `?room=授業名` を付けます
  (半角英数字のみ)。例:
  - 表示: `screen.html?room=monday1`
  - 投稿: `./?room=monday1`(QRコードには自動で付きます)
- **クロマキー用の緑背景**: `screen.html?bg=green`
  (OBS等でスライドにコメントだけを重ねる場合に)

## 注意事項

- 表示ページを**開いた後に**投稿されたコメントだけが流れます
  (過去のコメントは再生されません)
- 投稿されたコメントはFirestoreに残ります。たまったデータは
  Firebaseコンソールの「Firestore Database」→「データ」から
  `rooms` コレクションごと削除できます
- URLを知っていれば誰でも投稿できるため、荒らしが心配な場合は
  授業ごとに `?room=` を変えて運用してください(文字数制限・
  連投制限はアプリ側で行っています)
