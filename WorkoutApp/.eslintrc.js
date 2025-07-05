{
  "root": true,
  "extends": [
    "@react-native-community",
    "prettier"
  ],
  "plugins": [
    "prettier"
  ],
  "rules": {
    "prettier/prettier": ["error", {"endOfLine":"auto"}],
    "react/jsx-filename-extension": ["warn", { "extensions": [".js", ".jsx"] }],
    "react/react-in-jsx-scope": "off"
  }
}
