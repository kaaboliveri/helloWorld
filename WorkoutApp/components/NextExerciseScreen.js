import React from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity } from 'react-native';
import { globalStyles, colors, typography, spacing, cardStyle } from '../styles/globalStyles';

const NextExerciseScreen = ({ route, navigation }) => {
  const { remainingExercises, currentDayName, allSessionsForDay } = route.params;

  const startNextExercise = (exercise) => {
    // Need to pass all exercises of the current session segment (warmup, cardio, workout)
    // to WorkoutInProgressScreen for it to calculate the *next* remaining ones.
    // This logic might need refinement based on how `remainingExercises` is structured.
    // For now, assume `exercise` is complete and we can start it.
     if (exercise.sets > 0) {
        navigation.replace('WorkoutInProgress', {
            exercise: exercise,
            // Pass along the context needed for subsequent "next exercise" calculations
            currentSessionExercises: route.params.currentSessionExercises,
            currentExerciseId: exercise.id,
            currentDayName: currentDayName,
            allSessionsForDay: allSessionsForDay
        });
    } else {
        alert(`L'exercice '${exercise.name}' n'a pas de séries définies.`);
    }
  };

  if (!remainingExercises || remainingExercises.length === 0) {
    return (
      <View style={globalStyles.container}>
        <Text style={globalStyles.titleText}>🎉 Séance Terminée ! 🎉</Text>
        <Text style={styles.infoText}>Tous les exercices de cette section sont complétés.</Text>
        <TouchableOpacity
            style={[globalStyles.button, styles.navButton]}
            onPress={() => navigation.popToTop()}
        >
          <Text style={globalStyles.buttonText}>Retour au Calendrier</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={globalStyles.container}>
      <Text style={globalStyles.titleText}>Exercices Restants</Text>
      <FlatList
        data={remainingExercises}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[cardStyle, styles.exerciseItemPressable]}
            onPress={() => startNextExercise(item)}
          >
            <Text style={styles.exerciseNameText}>{item.name}</Text>
            <Text style={styles.exerciseDetailText}>
              {item.sets} séries x {item.reps} reps {item.weight && `- ${item.weight}`}
            </Text>
          </TouchableOpacity>
        )}
        contentContainerStyle={{ paddingBottom: spacing.l }}
      />
      <TouchableOpacity
        style={[globalStyles.button, styles.navButton, styles.endSessionButton]}
        onPress={() => navigation.popToTop()}
      >
        <Text style={globalStyles.buttonText}>Terminer la Séance</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  // globalStyles.container and globalStyles.titleText are used
  infoText: {
    fontSize: typography.fontSizeTitle,
    textAlign: 'center',
    marginBottom: spacing.xl,
    color: colors.textLight,
  },
  exerciseItemPressable: { // Styles for the TouchableOpacity wrapping exercise details
    // cardStyle is applied directly
     // marginBottom is handled by cardStyle
  },
  exerciseNameText: {
    fontSize: typography.fontSizeTitle,
    fontWeight: typography.fontWeightBold,
    color: colors.primary,
  },
  exerciseDetailText: {
    fontSize: typography.fontSizeBody,
    color: colors.text,
    marginTop: spacing.xs,
  },
  navButton: { // Common style for navigation buttons at the bottom
    marginTop: spacing.l,
  },
  endSessionButton: {
    backgroundColor: colors.success,
  }
  // globalStyles.buttonText is used
});

export default NextExerciseScreen;
