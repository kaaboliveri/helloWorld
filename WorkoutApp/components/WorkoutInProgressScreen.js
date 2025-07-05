import React, { useState, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Vibration, AppState } from 'react-native';

const DURATION_EFFORT = 30; // secondes
const DURATION_REST = 60; // secondes

const WorkoutInProgressScreen = ({ route, navigation }) => {
  const { exercise, currentSessionExercises, currentExerciseId, currentDayName, allSessionsForDay } = route.params;
  const [currentSet, setCurrentSet] = useState(1);
  const [isResting, setIsResting] = useState(false);
  const [timeLeft, setTimeLeft] = useState(DURATION_EFFORT);
  const [isTimerActive, setIsTimerActive] = useState(false);

  const intervalRef = useRef(null);
  const appState = useRef(AppState.currentState);

  // Handle AppState changes for timer pausing (basic)
  useEffect(() => {
    const subscription = AppState.addEventListener('change', nextAppState => {
      if (appState.current.match(/inactive|background/) && nextAppState === 'active') {
        console.log('App has come to the foreground!');
        // Potentially resume timer or notify user, for now, just log
      }
      appState.current = nextAppState;
      // console.log('AppState', appState.current);
      // If app goes to background, timer should ideally be paused or handled with background tasks
      // For MVP, we might just stop it or accept it might drift if not using advanced background features
      if (appState.current !== 'active' && intervalRef.current) {
        // clearInterval(intervalRef.current); // Simple pause
        // setIsTimerActive(false);
      }
    });

    return () => {
      subscription.remove();
      clearInterval(intervalRef.current);
    };
  }, []);


  useEffect(() => {
    if (!isTimerActive) {
      clearInterval(intervalRef.current);
      return;
    }

    setTimeLeft(isResting ? DURATION_REST : DURATION_EFFORT); // Reset time for new phase

    intervalRef.current = setInterval(() => {
      setTimeLeft((prevTime) => {
        if (prevTime <= 1) { // Timer reaches 0
          Vibration.vibrate(Platform.OS === "ios" ? [100, 200, 100] : 500); // Simple vibration

          if (isResting) { // Was resting, now start next set
            if (currentSet < exercise.sets) {
              setCurrentSet(prev => prev + 1);
              setIsResting(false);
              return DURATION_EFFORT;
            } else { // All sets done
              clearInterval(intervalRef.current);
              setIsTimerActive(false);
              // TODO: Handle exercise completion logic (US4)
              console.log("Exercise finished!");
              return 0;
            }
          } else { // Was effort, now start rest (if not last set)
            if (currentSet < exercise.sets) {
              setIsResting(true);
              return DURATION_REST;
            } else { // Last set effort done
              clearInterval(intervalRef.current);
              setIsTimerActive(false);
               // TODO: Handle exercise completion logic (US4)
              console.log("Exercise finished!");
              return 0;
            }
          }
        }
        return prevTime - 1;
      });
    }, 1000);

    return () => clearInterval(intervalRef.current);
  }, [isTimerActive, currentSet, isResting, exercise.sets]);

  const handleStartPauseToggle = () => {
    if (currentSet > exercise.sets) return; // Exercise already finished
    setIsTimerActive(!isTimerActive);
  };

  const handleSkipToRest = () => {
    if (isTimerActive && !isResting && currentSet <= exercise.sets) {
      Vibration.vibrate();
      setIsResting(true);
      setTimeLeft(DURATION_REST); // Manually trigger useEffect update for timer logic
    }
  };

  const handleSkipToNextSet = () => {
     if (isTimerActive && isResting && currentSet < exercise.sets) {
      Vibration.vibrate();
      setCurrentSet(prev => prev + 1);
      setIsResting(false);
      setTimeLeft(DURATION_EFFORT);
    }
  };

  const handleFinishExerciseEarly = () => {
    clearInterval(intervalRef.current);
    setIsTimerActive(false);
    console.log("Exercise marked as finished early by user.");
    navigateToNextOrFinish();
  };

  const navigateToNextOrFinish = () => {
    const currentIndex = currentSessionExercises.findIndex(ex => ex.id === currentExerciseId);
    const remaining = currentSessionExercises.slice(currentIndex + 1);

    navigation.replace('NextExercise', {
        remainingExercises: remaining,
        currentSessionExercises: currentSessionExercises, // Pass this along if needed by NextExerciseScreen for further chaining
        currentDayName: currentDayName,
        allSessionsForDay: allSessionsForDay
    });
  };

  // Update useEffect for exercise completion
  useEffect(() => {
    if (!isTimerActive) {
      // If timer is stopped and all sets were meant to be done (or was manually stopped at end)
      if (currentSet > exercise.sets && exercise.sets > 0) { // exercise.sets > 0 ensures it's not cardio
         console.log("All sets completed, navigating to next.");
         navigateToNextOrFinish();
      }
      clearInterval(intervalRef.current);
      return;
    }

    // Timer starting or phase changing
    setTimeLeft(isResting ? DURATION_REST : DURATION_EFFORT);

    intervalRef.current = setInterval(() => {
      setTimeLeft((prevTime) => {
        if (prevTime <= 1) {
          Vibration.vibrate(Platform.OS === "ios" ? [100, 200, 100] : 500);

          if (isResting) {
            if (currentSet < exercise.sets) {
              setCurrentSet(prev => prev + 1);
              setIsResting(false);
              return DURATION_EFFORT;
            } else {
              clearInterval(intervalRef.current);
              setIsTimerActive(false);
              console.log("Exercise finished after rest!");
              // navigateToNextOrFinish(); // This will be caught by the !isTimerActive useEffect above
              return 0; // Stop timer
            }
          } else {
            if (currentSet < exercise.sets) {
              setIsResting(true);
              return DURATION_REST;
            } else {
              clearInterval(intervalRef.current);
              setIsTimerActive(false);
              console.log("Exercise finished after effort!");
              // navigateToNextOrFinish(); // This will be caught by the !isTimerActive useEffect above
              return 0; // Stop timer
            }
          }
        }
        return prevTime - 1;
      });
    }, 1000);

    return () => clearInterval(intervalRef.current);
  }, [isTimerActive, currentSet, isResting, exercise.sets]);

  const totalSets = exercise.sets || (exercise.duration ? 1 : 0); // If duration based, consider it as 1 "set" for UI

  return (
    <View style={styles.container}>
      <Text style={styles.exerciseName}>{exercise.name}</Text>
      <Text style={styles.setInfo}>Série: {Math.min(currentSet, totalSets)} / {totalSets}</Text>

      <View style={styles.timerContainer}>
        <Text style={styles.timerPhase}>{isResting ? "Repos" : "Effort"}</Text>
        <Text style={styles.timerText}>{timeLeft}s</Text>
      </View>

      <TouchableOpacity
        style={styles.mainButton}
        onPress={handleStartPauseToggle}
        disabled={currentSet > totalSets && totalSets > 0} // Disable if all sets done
      >
        <Text style={styles.buttonText}>
          {currentSet > totalSets && totalSets > 0 ? "Exercice Terminé" : (isTimerActive ? "Pause" : "Démarrer")}
        </Text>
      </TouchableOpacity>

      {isTimerActive && !isResting && currentSet <= totalSets && totalSets > 0 && (
        <TouchableOpacity style={styles.skipButton} onPress={handleSkipToRest}>
          <Text style={styles.buttonText}>Passer au Repos</Text>
        </TouchableOpacity>
      )}
      {isTimerActive && isResting && currentSet < totalSets && totalSets > 0 && (
         <TouchableOpacity style={styles.skipButton} onPress={handleSkipToNextSet}>
          <Text style={styles.buttonText}>Passer à la Série Suivante</Text>
        </TouchableOpacity>
      )}

      {/* US4: Button to finish exercise and go to next */}
      <TouchableOpacity
        style={styles.finishButton}
        onPress={handleFinishExerciseEarly}
        // disabled={currentSet > totalSets && totalSets > 0} // Can be always active
        >
        <Text style={styles.buttonText}>Terminer l'exercice & Voir Suite</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
    backgroundColor: '#fff',
  },
  exerciseName: {
    fontSize: 28,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 20,
  },
  setInfo: {
    fontSize: 22,
    marginBottom: 30,
  },
  timerContainer: {
    alignItems: 'center',
    marginBottom: 40,
  },
  timerPhase: {
    fontSize: 24,
    color: '#555',
    marginBottom: 10,
  },
  timerText: {
    fontSize: 72,
    fontWeight: 'bold',
    color: '#007bff',
  },
  mainButton: {
    backgroundColor: '#007bff',
    paddingVertical: 15,
    paddingHorizontal: 40,
    borderRadius: 8,
    marginBottom: 15,
    width: '80%',
    alignItems: 'center',
  },
  skipButton: {
    backgroundColor: '#ffc107',
    paddingVertical: 10,
    paddingHorizontal: 30,
    borderRadius: 8,
    marginBottom: 15,
    width: '80%',
    alignItems: 'center',
  },
  finishButton: {
    backgroundColor: '#28a745',
    paddingVertical: 10,
    paddingHorizontal: 30,
    borderRadius: 8,
    marginTop: 20, // Give some space
    width: '80%',
    alignItems: 'center',
  },
  buttonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
});

export default WorkoutInProgressScreen;
