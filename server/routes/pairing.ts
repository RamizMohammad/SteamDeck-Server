import express from 'express';
import { ObjectId } from 'mongodb';
import { getUsersCollection } from '../db/mongodb';
import { authMiddleware, AuthRequest } from '../utils/auth';

const router = express.Router();

router.post('/pairing', authMiddleware, async (req: AuthRequest, res) => {
  try {
    const { pairingCode } = req.body;

    if (!pairingCode) {
      return res.status(400).json({ error: 'Pairing code is required' });
    }

    const users = await getUsersCollection();
    await users.updateOne(
      { _id: new ObjectId(req.userId) },
      {
        $set: { pairingCode },
        $push: {
          activityLog: {
            ts: new Date(),
            type: 'info',
            msg: `Pairing code set to ${pairingCode}`,
            raw: { pairingCode }
          }
        }
      }
    );

    res.json({ success: true, pairingCode });
  } catch (error) {
    console.error('Pairing error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

export default router;
