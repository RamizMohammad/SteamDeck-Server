import dotenv from 'dotenv';
import { Collection, Db, MongoClient, ObjectId } from 'mongodb';

dotenv.config();

let client: MongoClient | null = null;
let db: Db | null = null;

export interface Program {
  id: string;
  name: string;
  iconUrl: string;
  exec: string;
  meta?: { source?: string };
  addedAt: Date;
}

export interface ActivityLogEntry {
  ts: Date;
  type: 'info' | 'error' | 'warn';
  msg: string;
  raw?: any;
}

export interface User {
  _id?: ObjectId;
  email: string;
  passwordHash: string;
  pairingCode?: string;
  programsFetched: boolean;
  programs: Program[];
  activityLog: ActivityLogEntry[];
  createdAt: Date;
}

export async function connectToMongoDB(): Promise<Db> {
  if (db) return db;

  const uri = "mongodb+srv://steamdeck:9517@stemdeck.h9p3m3i.mongodb.net/";

  if (!uri || uri.trim() === '') {
    throw new Error('MONGODB_URI is not set in environment variables. Please add your MongoDB connection string to the .env file.');
  }

  try {
    client = new MongoClient(uri);
    await client.connect();
    db = client.db('streamdeck');
    console.log('✅ Connected to MongoDB');
    return db;
  } catch (error) {
    console.error('❌ MongoDB connection error:', error);
    throw error;
  }
}

export async function getUsersCollection(): Promise<Collection<User>> {
  const database = await connectToMongoDB();
  return database.collection<User>('users');
}

export async function closeMongoConnection(): Promise<void> {
  if (client) {
    await client.close();
    client = null;
    db = null;
    console.log('MongoDB connection closed');
  }
}
