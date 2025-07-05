import React from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ScrollView } from 'react-native';

const ExerciseDetail = ({ exercise, onStartExercise }) => (
  <TouchableOpacity style={styles.exerciseItem} onPress={() => onStartExercise(exercise)}>
    <Text style={styles.exerciseName}>{exercise.name}</Text>
    {exercise.sets && exercise.reps && <Text style={styles.exerciseInfo}>Séries: {exercise.sets}, Répétitions: {exercise.reps}</Text>}
    {exercise.weight && <Text style={styles.exerciseInfo}>Poids: {exercise.weight}</Text>}
    {exercise.duration && <Text style={styles.exerciseInfo}>Durée: {exercise.duration} min</Text>}
    {exercise.targetArea && <Text style={styles.exerciseInfo}>Zone Cible: {exercise.targetArea}</Text>}
    {exercise.notes && <Text style={styles.exerciseNotes}>Notes: {exercise.notes}</Text>}
  </TouchableOpacity>
);

const SessionDetailScreen = ({ route, navigation }) => {
  if (!route.params || !route.params.dayName || !route.params.sessions) {
    // Fallback UI or error message if essential params are missing
    return (
      <View style={globalStyles.container}>
        <Text style={globalStyles.titleText}>Erreur</Text>
        <Text style={styles.noSessionInfoText}>
          Impossible de charger les détails de la séance. Paramètres manquants.
        </Text>
        <TouchableOpacity style={globalStyles.button} onPress={() => navigation.goBack()}>
            <Text style={globalStyles.buttonText}>Retour</Text>
        </TouchableOpacity>
      </View>
    );
  }
  const { dayName, sessions } = route.params;

  const startExercise = (exercise, currentSectionExercisesList) => {
    console.log("Attempting to start exercise:", exercise.name);
    const validSectionExercises = Array.isArray(currentSectionExercisesList) ? currentSectionExercisesList : [];

    if (exercise.sets > 0 || (exercise.duration && !exercise.sets)) {
        navigation.navigate('WorkoutInProgress', {
            exercise: exercise,
            currentSessionExercises: validSectionExercises,
            currentExerciseId: exercise.id,
            currentDayName: dayName,
            allSessionsForDay: sessions
        });
    } else {
        alert(`L'exercice '${exercise.name}' n'a pas de séries ou de durée définie pour le suivi interactif.`);
    }
  };

  const renderSection = (title, sectionDataList) => {
    if (!sectionDataList || sectionDataList.length === 0) return null;
    return (
      <View style={styles.sectionContainer}>
        <Text style={styles.sectionTitleText}>{title}</Text>
        <FlatList
          data={sectionDataList}
          renderItem={({ item }) => (
            <ExerciseDetail
              exercise={item}
              onStartExercise={startExercise}
              sectionExercises={sectionDataList}
            />
          )}
          keyExtractor={(item) => item.id}
          scrollEnabled={false}
        />
      </View>
    );
  };

  const structuredSession = sessions.find(s => !s.isAlternate && (s.warmUp || s.cardio || s.workout));

  if (!structuredSession) {
    const anySession = sessions[0];
    let message = `Pas de séance de musculation détaillée pour ${dayName} aujourd'hui.`;
    if (anySession) {
        message = `${anySession.name || dayName} ${(anySession.location && anySession.location !== "Unknown") ? `à ${anySession.location}` : ''}. ${anySession.notes || ""}`;
    }

    return (
      <View style={styles.container}>
        <Text style={styles.pageTitle}>{dayName}</Text>
        <Text style={styles.noSessionText}>{message}</Text>
      </View>
    );
  }


  return (
    <ScrollView style={styles.container}>
      <Text style={styles.pageTitle}>{structuredSession.name}</Text>
      <Text style={styles.pageSubtitle}>{structuredSession.schedule} @ {structuredSession.location}</Text>

      {renderSection("Échauffement", structuredSession.warmUp)}
      {renderSection("Cardio", structuredSession.cardio)}
      {renderSection("Workout", structuredSession.workout)}

    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 20,
    backgroundColor: '#f9f9f9',
  },
  pageTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 5,
  },
  pageSubtitle: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    marginBottom: 20,
  },
  sectionContainer: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#333',
    marginBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
    paddingBottom: 5,
  },
  exerciseItem: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 8,
    marginBottom: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  exerciseName: {
    fontSize: 17,
    fontWeight: 'bold',
    color: '#007bff',
  },
  exerciseInfo: {
    fontSize: 14,
    color: '#454545',
    marginTop: 3,
  },
  exerciseNotes: {
    fontSize: 13,
    color: '#777',
    fontStyle: 'italic',
    marginTop: 5,
  },
  noSessionText: {
    fontSize: 18,
    textAlign: 'center',
    marginTop: 50,
    color: '#555',
  }
});

export default SessionDetailScreen;
