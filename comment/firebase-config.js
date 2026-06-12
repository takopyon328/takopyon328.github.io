// =====================================================================
// Firebase 設定ファイル
// README.md の手順に従って、Firebaseコンソールからコピーした設定を
// 下の firebaseConfig に貼り付けてください。
// =====================================================================
export const firebaseConfig = {
  apiKey: "ここにapiKeyを貼り付け",
  authDomain: "ここにauthDomainを貼り付け",
  projectId: "ここにprojectIdを貼り付け",
  storageBucket: "ここにstorageBucketを貼り付け",
  messagingSenderId: "ここにmessagingSenderIdを貼り付け",
  appId: "ここにappIdを貼り付け"
};

// 設定が貼り付けずみかどうかの判定(編集不要)
export const isConfigured = !firebaseConfig.apiKey.includes("ここに");
