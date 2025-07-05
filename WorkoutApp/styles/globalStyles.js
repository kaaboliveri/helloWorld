// WorkoutApp/styles/globalStyles.js

export const colors = {
  primary: '#007bff', // Un bleu classique pour les actions principales
  primaryDark: '#0056b3',
  secondary: '#6c757d', // Un gris pour les actions secondaires ou informations
  accent: '#ffc107', // Jaune pour les accents, timers, etc.
  success: '#28a745', // Vert pour les confirmations, achèvements
  danger: '#dc3545', // Rouge pour les erreurs ou alertes
  light: '#f8f9fa', // Fond clair
  dark: '#343a40', // Texte foncé
  text: '#212529',
  textLight: '#6c757d',
  background: '#ffffff',
  backgroundAlt: '#f0f0f0', // Pour les fonds légèrement différents
  border: '#ced4da',
  listItemBackground: '#ffffff',
};

export const typography = {
  fontFamilyDefault: null, // Utilise la police système par défaut
  fontSizeH1: 32,
  fontSizeH2: 28,
  fontSizeH3: 24,
  fontSizeH4: 20,
  fontSizeTitle: 18,
  fontSizeBody: 16,
  fontSizeSmall: 14,
  fontSizeCaption: 12,

  fontWeightBold: 'bold',
  fontWeightNormal: 'normal',
  fontWeightLight: '300',
};

export const spacing = {
  xs: 4,
  s: 8,
  m: 16,
  l: 24,
  xl: 32,
  xxl: 48,
};

export const globalStyles = {
  container: {
    flex: 1,
    backgroundColor: colors.backgroundAlt,
    paddingHorizontal: spacing.m,
    paddingTop: spacing.l,
  },
  titleText: {
    fontSize: typography.fontSizeH3,
    fontWeight: typography.fontWeightBold,
    color: colors.text,
    textAlign: 'center',
    marginBottom: spacing.m,
  },
  subtitleText: {
    fontSize: typography.fontSizeTitle,
    color: colors.textLight,
    textAlign: 'center',
    marginBottom: spacing.l,
  },
  button: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.m - 4, // 12
    paddingHorizontal: spacing.l,
    borderRadius: spacing.s,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50,
  },
  buttonText: {
    color: colors.background,
    fontSize: typography.fontSizeBody,
    fontWeight: typography.fontWeightBold,
  },
  // ... d'autres styles globaux si nécessaire
};

// Vous pouvez aussi créer des styles spécifiques pour des composants communs
// Par exemple, un style pour les cartes:
export const cardStyle = {
  backgroundColor: colors.listItemBackground,
  borderRadius: spacing.s,
  padding: spacing.m,
  marginBottom: spacing.m,
  shadowColor: colors.dark,
  shadowOffset: { width: 0, height: 2 },
  shadowOpacity: 0.1,
  shadowRadius: 4,
  elevation: 3, // Pour Android
  borderWidth: 1,
  borderColor: colors.border,
};
