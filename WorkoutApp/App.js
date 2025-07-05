import React, { useState, useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform, Linking } from 'react-native';

import ErrorBoundary from './components/ErrorBoundary'; // Import ErrorBoundary
import CalendarScreen from './components/CalendarScreen';
import SessionDetailScreen from './components/SessionDetailScreen';
import WorkoutInProgressScreen from './components/WorkoutInProgressScreen'; // Import new screen

const Stack = createStackNavigator();
const PERSISTENCE_KEY = 'WORKOUTAPP_NAVIGATION_STATE_V1'; // Keep this for when AsyncStorage works

export default function App() {
// Temporarily comment out persistence logic if AsyncStorage is not installed
/*
  const [isReady, setIsReady] = useState(false);
  const [initialState, setInitialState] = useState();

  useEffect(() => {
    const restoreState = async () => {
      try {
        const savedStateString = await AsyncStorage.getItem(PERSISTENCE_KEY);
        const state = savedStateString ? JSON.parse(savedStateString) : undefined;

        if (state !== undefined) {
          setInitialState(state);
        }
      } catch (e) {
        console.error("Failed to load navigation state", e);
        // Handle error, e.g. by clearing state or logging
      } finally {
        setIsReady(true);
      }
    };

    if (!isReady) {
      restoreState();
    }
  }, [isReady]);

  const onStateChange = async (state) => {
    try {
      await AsyncStorage.setItem(PERSISTENCE_KEY, JSON.stringify(state));
    } catch (e) {
      console.error("Failed to save navigation state", e);
      // Handle error
    }
  };

  if (!isReady) {
    return null; // Ou un écran de chargement
  }

  return (
    <NavigationContainer
      initialState={initialState}
      onStateChange={onStateChange}
    >
      <Stack.Navigator initialRouteName="Calendar">
        <Stack.Screen
          name="Calendar"
          component={CalendarScreen}
          options={{ title: 'Ma Routine Hebdomadaire' }}
        />
        <Stack.Screen
          name="SessionDetail"
          component={SessionDetailScreen}
          // Dynamically set the title based on the session or day name
          options={({ route }) => {
            let title = `Détail - ${route.params.dayName}`; // Default title
            if (route.params.sessions && route.params.sessions.length > 0) {
              const mainSession = route.params.sessions.find(s => !s.isAlternate && (s.warmUp || s.cardio || s.workout));
              if (mainSession) {
                title = mainSession.name;
              } else if (route.params.sessions[0]) { // Fallback to the first session's name (e.g., MMA or Rest)
                title = route.params.sessions[0].name;
              }
            }
            return {
              title: title,
              headerBackTitle: "Retour"
            };
          }}
        />
        <Stack.Screen
          name="WorkoutInProgress"
          component={WorkoutInProgressScreen}
          options={({ route }) => ({
            title: route.params.exercise ? route.params.exercise.name : 'Entraînement',
            headerBackTitle: "Détail"
          })}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
