import grpc
import user_service_pb2,user_service_pb2_grpc

def get_students(student_ids):
    with grpc.insecure_channel('localhost:50053') as channel:
        stub = user_service_pb2_grpc.UserServiceStub(channel)
        response = stub.GetStudentsByIds(user_service_pb2.GetStudentsRequest(user_id=student_ids))
        return response.students

if __name__ == "__main__":
    # student_ids = [1, 2, 3]
    students = get_students(student_ids)
    for s in students:
        print(f"{s.id}: {s.first_name} {s.last_name} <{s.email}>")
