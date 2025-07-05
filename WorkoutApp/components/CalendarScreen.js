import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, FlatList } from 'react-native';
import { getOrderedDays, getSessionsForDay } from '../data/workoutData'; // Assurez-vous que le chemin est correct

const CalendarScreen = ({ navigation }) => {
  const orderedDays = getOrderedDays();
  const [selectedDay, setSelectedDay] = useState(null);

  const handleDayPress = (dayName) => {
    setSelectedDay(dayName);
    // TODO: Navigate to SessionDetailScreen with sessions for dayName
    // For now, we'll just log it.
    const sessions = getSessionsForDay(dayName);
    console.log(`Selected Day: ${dayName}, Sessions:`, sessions.map(s=>s.name).join(', '));
    // Example navigation (to be implemented later):
    // navigation.navigate('SessionDetail', { dayName, sessions });
  };

  const renderItem = ({ item: dayName }) => {
    const sessions = getSessionsForDay(dayName);
    let displaySessions = "";
    if (sessions.length > 0) {
        displaySessions = sessions.map(s => s.name).join(' & ');
        if (sessions.some(s => s.isAlternate)) { // e.g. MMA Factory
            displaySessions += sessions.find(s=>s.isAlternate) ? ` (${sessions.find(s=>s.isAlternate).location})` : "";
        } else if (sessions.length === 1 && sessions[0].location) {
             displaySessions += ` (${sessions[0].location})`;
        }
    } else {
        displaySessions = "Repos";
    }


    return (
      <TouchableOpacity
        style={[
          styles.dayItem,
          selectedDay === dayName && styles.selectedDayItem,
        ]}
        onPress={() => handleDayPress(dayName)}>
        <Text style={styles.dayName}>{dayName.charAt(0).toUpperCase() + dayName.slice(1).toLowerCase()}</Text>
        <Text style={styles.sessionInfo}>{displaySessions}</Text>
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Programme de la Semaine</Text>
      <FlatList
        data={orderedDays}
        renderItem={renderItem}
        keyExtractor={(item) => item}
      />
      {selectedDay && (
        <View style={styles.debugSelection}>
          <Text>Jour sélectionné : {selectedDay}</Text>
          <Text>Séances : {getSessionsForDay(selectedDay).map(s => s.name).join(', ')}</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingTop: 50,
    paddingHorizontal: 20,
    backgroundColor: '#f0f0f0',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 20,
    textAlign: 'center',
  },
  dayItem: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 8,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#ddd',
  },
  selectedDayItem: {
    borderColor: '#007bff',
    borderWidth: 2,
    backgroundColor: '#e6f2ff',
  },
  dayName: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  sessionInfo: {
    fontSize: 14,
    color: '#555',
    marginTop: 5,
  },
  debugSelection: {
    padding: 10,
    marginTop: 10,
    backgroundColor: '#eee',
    borderRadius: 5,
  }
});

export default CalendarScreen;
