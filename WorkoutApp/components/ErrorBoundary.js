import React from 'react';
import { View, Text, StyleSheet, Button } from 'react-native';
import { colors, typography, spacing, globalStyles } from '../styles/globalStyles';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // You can also log the error to an error reporting service
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    this.setState({ errorInfo });
    // Example: logErrorToMyService(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      // You can render any custom fallback UI
      return (
        <View style={styles.container}>
          <Text style={styles.title}>Oops! Une erreur est survenue.</Text>
          <Text style={styles.message}>
            Nous sommes désolés pour ce désagrément. Veuillez essayer de redémarrer l'application.
          </Text>
          {__DEV__ && this.state.error && ( // Show more details in DEV mode
            <View style={styles.devErrorDetails}>
              <Text style={styles.devTitle}>Détails de l'erreur (DEV):</Text>
              <Text style={styles.devText}>{this.state.error.toString()}</Text>
              {this.state.errorInfo && (
                <Text style={styles.devText}>{this.state.errorInfo.componentStack}</Text>
              )}
            </View>
          )}
          {/* On pourrait ajouter un bouton pour tenter de recharger ou effacer l'état si pertinent */}
          {/* <Button title="Recharger" onPress={() => {}} /> */}
        </View>
      );
    }

    return this.props.children;
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.l,
    backgroundColor: colors.backgroundAlt,
  },
  title: {
    fontSize: typography.fontSizeH3,
    fontWeight: typography.fontWeightBold,
    color: colors.danger,
    textAlign: 'center',
    marginBottom: spacing.m,
  },
  message: {
    fontSize: typography.fontSizeBody,
    color: colors.text,
    textAlign: 'center',
    marginBottom: spacing.l,
  },
  devErrorDetails: {
    marginTop: spacing.l,
    padding: spacing.m,
    backgroundColor: colors.background,
    borderRadius: spacing.s,
    borderWidth: 1,
    borderColor: colors.border,
    width: '100%',
  },
  devTitle: {
    fontSize: typography.fontSizeTitle,
    fontWeight: typography.fontWeightBold,
    marginBottom: spacing.s,
  },
  devText: {
    fontSize: typography.fontSizeSmall,
    color: colors.textLight,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', // Monospace for stack traces
  }
});

export default ErrorBoundary;
